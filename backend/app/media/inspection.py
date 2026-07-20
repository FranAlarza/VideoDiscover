"""Isolated metadata inspection with yt-dlp and no media download."""

import asyncio
import multiprocessing
import os
import shutil
import threading
from collections.abc import Callable
from datetime import datetime
from multiprocessing.connection import Connection
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlsplit

from app.media.validation import (
    MediaUrlValidationService,
    NetworkSafetyChecker,
    UrlValidationError,
)
from app.models.inspection import MediaInspectionResponse
from app.models.media import ValidatedMediaUrl

_VIDEO_QUALITIES = {360, 480, 720, 1080, 1440, 2160}
_DEFAULT_NODE_24 = Path("/opt/homebrew/opt/node@24/bin/node")
_MAX_DURATION_SECONDS = 7 * 24 * 60 * 60
_MAX_ESTIMATED_SIZE = 10 * 1024**4

_ERROR_MESSAGES = {
    "private_media": "Este contenido es privado o requiere iniciar sesión.",
    "media_unavailable": "El contenido ya no está disponible.",
    "region_restricted": "Este contenido no está disponible desde tu ubicación.",
    "age_restricted": (
        "Este contenido requiere una verificación no disponible en el MVP."
    ),
    "drm_protected": "El contenido está protegido y no puede descargarse.",
    "playlist_not_supported": "Las listas de reproducción todavía no están soportadas.",
    "temporarily_blocked": "La plataforma ha rechazado temporalmente la solicitud.",
    "network_error": "La conexión se interrumpió durante el análisis.",
    "inspection_timeout": "El análisis ha superado el tiempo permitido.",
    "inspection_unavailable": "El servicio de análisis no está disponible.",
    "unknown_error": "No se ha podido analizar el contenido.",
}


class MediaInspectionError(RuntimeError):
    """Sanitized inspection failure safe for an API response."""

    def __init__(self, code: str, *, status_code: int) -> None:
        super().__init__(_ERROR_MESSAGES[code])
        self.code = code
        self.message = _ERROR_MESSAGES[code]
        self.status_code = status_code


class RawInspectionError(RuntimeError):
    """Internal yt-dlp failure that still needs classification."""


class _QuietYtDlpLogger:
    """Prevent raw extractor messages from reaching application stderr."""

    def debug(self, _message: str) -> None:
        pass

    def info(self, _message: str) -> None:
        pass

    def warning(self, _message: str) -> None:
        pass

    def error(self, _message: str) -> None:
        pass


class InspectionRunner(Protocol):
    def inspect(
        self, canonical_url: str, node_binary: str, timeout_seconds: float
    ) -> dict[str, Any]: ...

    def shutdown(self) -> None: ...


class ProcessInspectionRunner:
    """Run yt-dlp in a spawn process that can be terminated on timeout."""

    def __init__(
        self,
        *,
        worker_target: Callable[[Connection, str, str], None] | None = None,
    ) -> None:
        self._worker_target = worker_target or _yt_dlp_worker
        self._active_processes: set[multiprocessing.Process] = set()
        self._lock = threading.Lock()
        self._closed = False

    @property
    def active_process_count(self) -> int:
        with self._lock:
            return len(self._active_processes)

    def inspect(
        self, canonical_url: str, node_binary: str, timeout_seconds: float
    ) -> dict[str, Any]:
        with self._lock:
            if self._closed:
                raise MediaInspectionError("inspection_unavailable", status_code=503)

        context = multiprocessing.get_context("spawn")
        parent_connection, child_connection = context.Pipe(duplex=False)
        process = context.Process(
            target=self._worker_target,
            args=(child_connection, canonical_url, node_binary),
            daemon=True,
        )
        process.start()
        with self._lock:
            if self._closed:
                _stop_process(process)
                raise MediaInspectionError("inspection_unavailable", status_code=503)
            self._active_processes.add(process)
        child_connection.close()

        try:
            if not parent_connection.poll(timeout_seconds):
                _stop_process(process)
                raise MediaInspectionError("inspection_timeout", status_code=408)

            outcome = parent_connection.recv()
            process.join(timeout=1)
        except EOFError as error:
            raise MediaInspectionError(
                "inspection_unavailable", status_code=503
            ) from error
        finally:
            parent_connection.close()
            if process.is_alive():
                _stop_process(process)
            with self._lock:
                self._active_processes.discard(process)

        if outcome["status"] == "error":
            raise RawInspectionError(outcome["message"])
        result = outcome.get("result")
        if not isinstance(result, dict):
            raise MediaInspectionError("unknown_error", status_code=502)
        return result

    def shutdown(self) -> None:
        """Prevent new work and terminate every active inspection process."""
        with self._lock:
            self._closed = True
            active_processes = list(self._active_processes)
        for process in active_processes:
            if process.is_alive():
                _stop_process(process)
        with self._lock:
            self._active_processes.clear()


class MediaInspectionService:
    """Validate a URL, inspect it and expose a stable minimal contract."""

    def __init__(
        self,
        validator: MediaUrlValidationService,
        *,
        runner: InspectionRunner | None = None,
        node_binary: str | None = None,
        timeout_seconds: float = 25,
        maximum_concurrency: int = 1,
        thumbnail_checker: NetworkSafetyChecker | None = None,
    ) -> None:
        self._validator = validator
        self._runner = runner or ProcessInspectionRunner()
        self._node_binary = node_binary or _resolve_node_binary()
        self._timeout_seconds = timeout_seconds
        self._semaphore = asyncio.Semaphore(maximum_concurrency)
        self._thumbnail_checker = thumbnail_checker or NetworkSafetyChecker()

    async def inspect(self, raw_url: str) -> MediaInspectionResponse:
        validated = await self._validator.validate(raw_url)
        return await self.inspect_validated(validated)

    async def inspect_validated(
        self, validated: ValidatedMediaUrl
    ) -> MediaInspectionResponse:
        """Inspect a URL that already passed the canonical security validation."""
        if not self._node_binary:
            raise MediaInspectionError("inspection_unavailable", status_code=503)

        async with self._semaphore:
            try:
                raw_info = await asyncio.to_thread(
                    self._runner.inspect,
                    validated.canonical_url,
                    self._node_binary,
                    self._timeout_seconds,
                )
            except MediaInspectionError:
                raise
            except RawInspectionError as error:
                raise _classify_yt_dlp_error(str(error)) from error
            except (OSError, RuntimeError) as error:
                raise MediaInspectionError(
                    "inspection_unavailable", status_code=503
                ) from error

        result = _map_metadata(validated, raw_info)
        await self._validate_thumbnail(result)
        return result

    async def shutdown(self) -> None:
        shutdown = getattr(self._runner, "shutdown", None)
        if shutdown is not None:
            await asyncio.to_thread(shutdown)

    async def _validate_thumbnail(self, result: MediaInspectionResponse) -> None:
        if not result.thumbnail_url:
            return
        split = urlsplit(result.thumbnail_url)
        try:
            port = split.port or (443 if split.scheme == "https" else 80)
            await self._thumbnail_checker.ensure_public(split.hostname or "", port)
        except (ValueError, UrlValidationError):
            result.thumbnail_url = None


def _yt_dlp_worker(
    connection: Connection, canonical_url: str, node_binary: str
) -> None:
    try:
        from yt_dlp import YoutubeDL

        options = _build_yt_dlp_options(node_binary)
        with YoutubeDL(options) as downloader:
            result = downloader.extract_info(canonical_url, download=False)
            sanitized = downloader.sanitize_info(result)
            limited = _limit_ipc_metadata(sanitized)
        connection.send({"status": "ok", "result": limited})
    except Exception as error:  # yt-dlp exposes many extractor/network subclasses
        connection.send({"status": "error", "message": str(error)[:2000]})
    finally:
        connection.close()


def _build_yt_dlp_options(node_binary: str) -> dict[str, Any]:
    return {
        "skip_download": True,
        "simulate": True,
        "noplaylist": True,
        "extract_flat": False,
        "quiet": True,
        "no_warnings": True,
        "logger": _QuietYtDlpLogger(),
        "socket_timeout": 10,
        "retries": 1,
        "extractor_retries": 1,
        "js_runtimes": {"node": {"path": node_binary}},
        "remote_components": set(),
    }


def _stop_process(process: multiprocessing.Process) -> None:
    process.terminate()
    process.join(timeout=1)
    if process.is_alive():
        process.kill()
        process.join(timeout=1)


def _resolve_node_binary() -> str | None:
    configured = os.getenv("VD_NODE_BINARY")
    if configured:
        return configured
    if _DEFAULT_NODE_24.is_file():
        return str(_DEFAULT_NODE_24)
    return shutil.which("node")


def _map_metadata(
    validated: ValidatedMediaUrl, raw_info: dict[str, Any]
) -> MediaInspectionResponse:
    if raw_info.get("_type") in {"playlist", "multi_video"} or raw_info.get("entries"):
        raise MediaInspectionError("playlist_not_supported", status_code=400)
    if raw_info.get("is_live") or raw_info.get("live_status") == "is_live":
        raise MediaInspectionError("media_unavailable", status_code=400)
    extracted_id = raw_info.get("id")
    if isinstance(extracted_id, str) and extracted_id != validated.media_id:
        raise MediaInspectionError("unknown_error", status_code=502)

    title = _bounded_text(raw_info.get("title"), 200)
    if not title:
        raise MediaInspectionError("unknown_error", status_code=502)

    formats = raw_info.get("formats")
    safe_formats = formats[:500] if isinstance(formats, list) else []
    qualities = sorted(
        {
            quality
            for item in safe_formats
            if isinstance(item, dict)
            and item.get("vcodec") not in {None, "none"}
            and (quality := _quality_for_format(item)) is not None
        },
        reverse=True,
    )
    audio_available = any(
        isinstance(item, dict) and item.get("acodec") not in {None, "none"}
        for item in safe_formats
    )

    return MediaInspectionResponse(
        platform=validated.platform,
        media_id=validated.media_id,
        title=title,
        author=_first_text(raw_info, "uploader", "channel", "creator"),
        duration_seconds=_non_negative_int(raw_info.get("duration")),
        thumbnail_url=_safe_public_url(raw_info.get("thumbnail")),
        published_at=_published_date(raw_info.get("upload_date")),
        estimated_size=_estimated_size(safe_formats),
        video_qualities=qualities,
        audio_available=audio_available,
        is_live=False,
    )


def _classify_yt_dlp_error(message: str) -> MediaInspectionError:
    normalized = message.casefold()
    classifications: list[tuple[tuple[str, ...], str, int]] = [
        (("private video", "login required", "sign in"), "private_media", 400),
        (
            ("country", "geo restricted", "not available in your"),
            "region_restricted",
            400,
        ),
        (("not available", "video unavailable", "removed"), "media_unavailable", 404),
        (
            ("age-restricted", "age restricted", "confirm your age"),
            "age_restricted",
            400,
        ),
        (("drm", "digital rights management"), "drm_protected", 400),
        (("playlist",), "playlist_not_supported", 400),
        (
            ("429", "too many requests", "temporarily blocked"),
            "temporarily_blocked",
            429,
        ),
        (("network", "timed out", "connection", "http error"), "network_error", 503),
    ]
    for markers, code, status_code in classifications:
        if any(marker in normalized for marker in markers):
            return MediaInspectionError(code, status_code=status_code)
    return MediaInspectionError("unknown_error", status_code=502)


def _bounded_text(value: Any, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split()).strip()
    return cleaned[:limit] or None


def _first_text(data: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        if result := _bounded_text(data.get(key), 200):
            return result
    return None


def _non_negative_int(value: Any) -> int | None:
    if (
        not isinstance(value, int | float)
        or isinstance(value, bool)
        or not 0 <= value <= _MAX_DURATION_SECONDS
    ):
        return None
    return int(value)


def _published_date(value: Any) -> str | None:
    if not isinstance(value, str) or len(value) != 8 or not value.isdigit():
        return None
    try:
        parsed = datetime.strptime(value, "%Y%m%d").date()
    except ValueError:
        return None
    return parsed.isoformat()


def _estimated_size(formats: list[Any]) -> int | None:
    sizes = []
    for item in formats:
        if not isinstance(item, dict):
            continue
        size = item.get("filesize") or item.get("filesize_approx")
        if (
            isinstance(size, int | float)
            and not isinstance(size, bool)
            and 0 < size <= _MAX_ESTIMATED_SIZE
        ):
            sizes.append(int(size))
    return max(sizes, default=None)


def _quality_for_format(item: dict[str, Any]) -> int | None:
    dimensions = [
        value
        for key in ("width", "height")
        if isinstance((value := item.get(key)), int) and value > 0
    ]
    if not dimensions:
        return None
    reference = min(dimensions) if len(dimensions) == 2 else dimensions[0]
    return max(
        (quality for quality in _VIDEO_QUALITIES if quality <= reference),
        default=None,
    )


def _safe_public_url(value: Any) -> str | None:
    if not isinstance(value, str) or len(value) > 2048:
        return None
    try:
        split = urlsplit(value)
    except ValueError:
        return None
    if split.scheme not in {"http", "https"} or not split.hostname:
        return None
    if split.username is not None or split.password is not None:
        return None
    return value


def _limit_ipc_metadata(raw_info: Any) -> dict[str, Any]:
    """Drop secrets and cap data before it crosses the process pipe."""
    if not isinstance(raw_info, dict):
        return {}
    allowed_scalar_fields = {
        "id",
        "_type",
        "title",
        "uploader",
        "channel",
        "creator",
        "duration",
        "thumbnail",
        "upload_date",
        "is_live",
        "live_status",
    }
    limited = {
        key: _limit_scalar(value)
        for key, value in raw_info.items()
        if key in allowed_scalar_fields
    }
    if raw_info.get("entries"):
        limited["entries"] = True

    formats = raw_info.get("formats")
    if isinstance(formats, list):
        allowed_format_fields = {
            "width",
            "height",
            "vcodec",
            "acodec",
            "filesize",
            "filesize_approx",
        }
        limited["formats"] = [
            {
                key: _limit_scalar(value)
                for key, value in item.items()
                if key in allowed_format_fields
            }
            for item in formats[:500]
            if isinstance(item, dict)
        ]
    return limited


def _limit_scalar(value: Any) -> Any:
    if isinstance(value, str):
        return value[:2048]
    if isinstance(value, bool | int | float) or value is None:
        return value
    return None
