"""Layered validation for supported public media URLs."""

import asyncio
import ipaddress
import re
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit

import httpx

from app.models.media import Platform, ValidatedMediaUrl

DnsResolver = Callable[[str, int], Awaitable[list[str]]]
RedirectFetcher = Callable[[str], Awaitable[str | None]]

_YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
}
_TIKTOK_HOSTS = {
    "tiktok.com",
    "www.tiktok.com",
    "m.tiktok.com",
    "vm.tiktok.com",
    "vt.tiktok.com",
}
_YOUTUBE_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_TIKTOK_ID = re.compile(r"^\d{10,30}$")
_SHORT_CODE = re.compile(r"^[A-Za-z0-9_-]{5,40}$")
_TIKTOK_VIDEO_PATH = re.compile(r"^/@[^/]{1,64}/video/(?P<id>\d{10,30})/?$")
_CONTROL_CHARACTER = re.compile(r"[\x00-\x1f\x7f]")

_MESSAGES = {
    "empty_url": "Introduce una URL.",
    "url_too_long": "La dirección introducida es demasiado larga.",
    "invalid_url": "La dirección introducida no es válida.",
    "unsupported_scheme": "Solo se admiten direcciones HTTP o HTTPS.",
    "embedded_credentials": "La dirección no puede incluir credenciales.",
    "unsupported_platform": "Esta plataforma no está soportada en el MVP.",
    "playlist_not_supported": "Las listas de reproducción todavía no están soportadas.",
    "invalid_media_url": "La dirección no corresponde a un vídeo individual válido.",
    "blocked_network_target": "La dirección apunta a un destino de red no permitido.",
    "dns_resolution_failed": "No se ha podido verificar el destino de la dirección.",
    "redirect_not_allowed": "El enlace redirige a un destino no permitido.",
    "too_many_redirects": "El enlace contiene demasiadas redirecciones.",
    "redirect_loop": "El enlace contiene un bucle de redirecciones.",
    "short_link_unresolved": "No se ha podido resolver el enlace corto.",
}


class UrlValidationError(ValueError):
    """Stable functional error returned by URL validation."""

    def __init__(self, code: str, *, status_code: int = 400) -> None:
        super().__init__(_MESSAGES[code])
        self.code = code
        self.message = _MESSAGES[code]
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class ParsedMediaUrl:
    platform: Platform
    media_id: str
    canonical_url: str
    network_url: str
    hostname: str
    port: int
    requires_redirect: bool = False


class MediaUrlParser:
    """Parse supported URL shapes without accessing the network."""

    def parse(self, raw_url: str) -> ParsedMediaUrl:
        value = raw_url.strip()
        if not value:
            raise UrlValidationError("empty_url")
        if len(value) > 2048:
            raise UrlValidationError("url_too_long")
        if _CONTROL_CHARACTER.search(value):
            raise UrlValidationError("invalid_url")

        try:
            split = urlsplit(value)
            port = split.port
        except ValueError as error:
            raise UrlValidationError("invalid_url") from error

        scheme = split.scheme.lower()
        if scheme not in {"http", "https"}:
            raise UrlValidationError("unsupported_scheme")
        if split.username is not None or split.password is not None:
            raise UrlValidationError("embedded_credentials")
        if not split.hostname:
            raise UrlValidationError("invalid_url")

        try:
            hostname = split.hostname.encode("idna").decode("ascii").lower().rstrip(".")
        except UnicodeError as error:
            raise UrlValidationError("invalid_url") from error

        expected_port = 443 if scheme == "https" else 80
        if port not in {None, expected_port}:
            raise UrlValidationError("invalid_url")
        try:
            query = parse_qs(split.query, keep_blank_values=True, max_num_fields=20)
        except ValueError as error:
            raise UrlValidationError("invalid_url") from error

        if hostname in _YOUTUBE_HOSTS:
            return self._parse_youtube(hostname, split.path, query, scheme)
        if hostname in _TIKTOK_HOSTS:
            return self._parse_tiktok(hostname, split.path, scheme)
        raise UrlValidationError("unsupported_platform")

    def _parse_youtube(
        self,
        hostname: str,
        path: str,
        query: dict[str, list[str]],
        scheme: str,
    ) -> ParsedMediaUrl:
        if path.rstrip("/") == "/playlist":
            raise UrlValidationError("playlist_not_supported")
        if "list" in query and not query.get("v", [""])[0]:
            raise UrlValidationError("playlist_not_supported")

        if hostname == "youtu.be":
            media_id = path.strip("/")
        elif path.rstrip("/") == "/watch":
            media_id = query.get("v", [""])[0]
        else:
            segments = [segment for segment in path.split("/") if segment]
            media_id = (
                segments[1]
                if len(segments) == 2 and segments[0] in {"shorts", "live", "embed"}
                else ""
            )

        if not _YOUTUBE_ID.fullmatch(media_id):
            raise UrlValidationError("invalid_media_url")

        canonical = f"https://www.youtube.com/watch?{urlencode({'v': media_id})}"
        network_url = urlunsplit((scheme, hostname, path, "", ""))
        return ParsedMediaUrl(
            platform=Platform.YOUTUBE,
            media_id=media_id,
            canonical_url=canonical,
            network_url=network_url,
            hostname=hostname,
            port=443 if scheme == "https" else 80,
        )

    def _parse_tiktok(self, hostname: str, path: str, scheme: str) -> ParsedMediaUrl:
        if hostname in {"vm.tiktok.com", "vt.tiktok.com"}:
            short_code = path.strip("/")
            if not _SHORT_CODE.fullmatch(short_code):
                raise UrlValidationError("invalid_media_url")
            network_url = urlunsplit((scheme, hostname, f"/{short_code}", "", ""))
            return ParsedMediaUrl(
                platform=Platform.TIKTOK,
                media_id=short_code,
                canonical_url=network_url,
                network_url=network_url,
                hostname=hostname,
                port=443 if scheme == "https" else 80,
                requires_redirect=True,
            )

        match = _TIKTOK_VIDEO_PATH.fullmatch(path)
        if not match or not _TIKTOK_ID.fullmatch(match.group("id")):
            raise UrlValidationError("invalid_media_url")
        media_id = match.group("id")
        handle = path.split("/")[1]
        canonical = f"https://www.tiktok.com/{handle}/video/{media_id}"
        return ParsedMediaUrl(
            platform=Platform.TIKTOK,
            media_id=media_id,
            canonical_url=canonical,
            network_url=canonical,
            hostname=hostname,
            port=443 if scheme == "https" else 80,
        )


class NetworkSafetyChecker:
    """Require every resolved IPv4/IPv6 address to be globally routable."""

    def __init__(self, resolver: DnsResolver | None = None) -> None:
        self._resolver = resolver or _resolve_addresses

    async def ensure_public(self, hostname: str, port: int) -> None:
        try:
            addresses = await asyncio.wait_for(
                self._resolver(hostname, port), timeout=3
            )
        except (TimeoutError, OSError, socket.gaierror) as error:
            raise UrlValidationError(
                "dns_resolution_failed", status_code=503
            ) from error
        if not addresses:
            raise UrlValidationError("dns_resolution_failed", status_code=503)

        for raw_address in addresses:
            try:
                address = ipaddress.ip_address(raw_address)
            except ValueError as error:
                raise UrlValidationError(
                    "dns_resolution_failed", status_code=503
                ) from error
            if not address.is_global:
                raise UrlValidationError("blocked_network_target")


class MediaUrlValidationService:
    """Coordinate parsing, DNS safety and controlled short-link redirects."""

    def __init__(
        self,
        *,
        parser: MediaUrlParser | None = None,
        network_checker: NetworkSafetyChecker | None = None,
        redirect_fetcher: RedirectFetcher | None = None,
        max_redirects: int = 5,
    ) -> None:
        self._parser = parser or MediaUrlParser()
        self._network_checker = network_checker or NetworkSafetyChecker()
        self._redirect_fetcher = redirect_fetcher or _fetch_redirect
        self._max_redirects = max_redirects

    async def validate(self, raw_url: str) -> ValidatedMediaUrl:
        parsed = self._parser.parse(raw_url)
        await self._network_checker.ensure_public(parsed.hostname, parsed.port)
        if parsed.requires_redirect:
            parsed = await self._resolve_short_link(parsed)

        return ValidatedMediaUrl(
            platform=parsed.platform,
            media_id=parsed.media_id,
            canonical_url=parsed.canonical_url,
        )

    async def _resolve_short_link(self, initial: ParsedMediaUrl) -> ParsedMediaUrl:
        current = initial
        visited = {current.network_url}
        for _ in range(self._max_redirects):
            location = await self._redirect_fetcher(current.network_url)
            if location is None:
                raise UrlValidationError("short_link_unresolved", status_code=503)
            target = urljoin(current.network_url, location)
            if target in visited:
                raise UrlValidationError("redirect_loop")
            visited.add(target)

            try:
                current = self._parser.parse(target)
            except UrlValidationError as error:
                raise UrlValidationError("redirect_not_allowed") from error
            await self._network_checker.ensure_public(current.hostname, current.port)
            if not current.requires_redirect:
                return current
        raise UrlValidationError("too_many_redirects")


async def _resolve_addresses(hostname: str, port: int) -> list[str]:
    loop = asyncio.get_running_loop()
    records = await loop.getaddrinfo(
        hostname,
        port,
        family=socket.AF_UNSPEC,
        type=socket.SOCK_STREAM,
    )
    return list({record[4][0] for record in records})


async def _fetch_redirect(url: str) -> str | None:
    headers = {"Range": "bytes=0-0", "User-Agent": "VideoDownloader/0.1"}
    timeout = httpx.Timeout(5.0)
    async with (
        httpx.AsyncClient(follow_redirects=False, timeout=timeout) as client,
        client.stream("GET", url, headers=headers) as response,
    ):
        if response.is_redirect:
            return response.headers.get("location")
        return None
