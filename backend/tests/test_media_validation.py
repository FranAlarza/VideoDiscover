import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.media.validation import (
    MediaUrlParser,
    MediaUrlValidationService,
    NetworkSafetyChecker,
    UrlValidationError,
)
from app.models.media import Platform, ValidatedMediaUrl


@pytest.mark.parametrize(
    ("url", "platform", "media_id", "canonical"),
    [
        (
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            Platform.YOUTUBE,
            "dQw4w9WgXcQ",
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        ),
        (
            "https://youtu.be/dQw4w9WgXcQ?t=20",
            Platform.YOUTUBE,
            "dQw4w9WgXcQ",
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        ),
        (
            "https://www.youtube.com/shorts/dQw4w9WgXcQ",
            Platform.YOUTUBE,
            "dQw4w9WgXcQ",
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        ),
        (
            "https://WWW.YOUTUBE.COM/live/dQw4w9WgXcQ",
            Platform.YOUTUBE,
            "dQw4w9WgXcQ",
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        ),
        (
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PL123",
            Platform.YOUTUBE,
            "dQw4w9WgXcQ",
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        ),
        (
            "https://www.tiktok.com/@scout2015/video/6718335390845095173",
            Platform.TIKTOK,
            "6718335390845095173",
            "https://www.tiktok.com/@scout2015/video/6718335390845095173",
        ),
    ],
)
def test_parser_accepts_supported_individual_urls(
    url: str, platform: Platform, media_id: str, canonical: str
) -> None:
    result = MediaUrlParser().parse(url)

    assert result.platform is platform
    assert result.media_id == media_id
    assert result.canonical_url == canonical


@pytest.mark.parametrize(
    ("url", "error_code"),
    [
        ("", "empty_url"),
        ("file:///tmp/video", "unsupported_scheme"),
        ("https://user:secret@youtube.com/watch?v=dQw4w9WgXcQ", "embedded_credentials"),
        ("https://youtube.com.example.org/watch?v=dQw4w9WgXcQ", "unsupported_platform"),
        ("https://evil-youtube.com/watch?v=dQw4w9WgXcQ", "unsupported_platform"),
        ("https://www.youtube.com/playlist?list=PL123", "playlist_not_supported"),
        ("https://www.youtube.com/watch?list=PL123", "playlist_not_supported"),
        ("https://www.youtube.com/@creator", "invalid_media_url"),
        ("https://www.tiktok.com/@creator", "invalid_media_url"),
        ("https://www.youtube.com:8443/watch?v=dQw4w9WgXcQ", "invalid_url"),
    ],
)
def test_parser_rejects_unsupported_or_unsafe_urls(url: str, error_code: str) -> None:
    with pytest.raises(UrlValidationError) as captured:
        MediaUrlParser().parse(url)

    assert captured.value.code == error_code


def test_parser_marks_tiktok_short_link_for_redirect() -> None:
    result = MediaUrlParser().parse("https://vm.tiktok.com/ZM123abc/")

    assert result.requires_redirect is True
    assert result.hostname == "vm.tiktok.com"


@pytest.mark.parametrize(
    "addresses",
    [
        ["127.0.0.1"],
        ["10.0.0.1"],
        ["169.254.1.1"],
        ["::1"],
        ["fe80::1"],
        ["2606:4700:4700::1111", "192.168.1.2"],
    ],
)
def test_network_checker_rejects_any_non_public_address(addresses: list[str]) -> None:
    async def resolver(_hostname: str, _port: int) -> list[str]:
        return addresses

    checker = NetworkSafetyChecker(resolver)

    with pytest.raises(UrlValidationError) as captured:
        asyncio.run(checker.ensure_public("www.youtube.com", 443))

    assert captured.value.code == "blocked_network_target"


def test_network_checker_accepts_only_public_addresses() -> None:
    async def resolver(_hostname: str, _port: int) -> list[str]:
        return ["8.8.8.8", "2606:4700:4700::1111"]

    asyncio.run(NetworkSafetyChecker(resolver).ensure_public("www.youtube.com", 443))


def test_validation_resolves_safe_tiktok_short_link() -> None:
    checked_hosts: list[str] = []

    async def resolver(hostname: str, _port: int) -> list[str]:
        checked_hosts.append(hostname)
        return ["8.8.8.8"]

    async def redirect_fetcher(_url: str) -> str:
        return "https://www.tiktok.com/@scout2015/video/6718335390845095173"

    service = MediaUrlValidationService(
        network_checker=NetworkSafetyChecker(resolver),
        redirect_fetcher=redirect_fetcher,
    )

    result = asyncio.run(service.validate("https://vm.tiktok.com/ZM123abc/"))

    assert result.media_id == "6718335390845095173"
    assert checked_hosts == ["vm.tiktok.com", "www.tiktok.com"]


def test_validation_rejects_redirect_to_unapproved_host() -> None:
    async def resolver(_hostname: str, _port: int) -> list[str]:
        return ["8.8.8.8"]

    async def redirect_fetcher(_url: str) -> str:
        return "http://127.0.0.1/private"

    service = MediaUrlValidationService(
        network_checker=NetworkSafetyChecker(resolver),
        redirect_fetcher=redirect_fetcher,
    )

    with pytest.raises(UrlValidationError) as captured:
        asyncio.run(service.validate("https://vm.tiktok.com/ZM123abc/"))

    assert captured.value.code == "redirect_not_allowed"


def test_validation_detects_redirect_loop() -> None:
    async def resolver(_hostname: str, _port: int) -> list[str]:
        return ["8.8.8.8"]

    async def redirect_fetcher(url: str) -> str:
        return url

    service = MediaUrlValidationService(
        network_checker=NetworkSafetyChecker(resolver),
        redirect_fetcher=redirect_fetcher,
    )

    with pytest.raises(UrlValidationError) as captured:
        asyncio.run(service.validate("https://vm.tiktok.com/ZM123abc/"))

    assert captured.value.code == "redirect_loop"


def test_validate_endpoint_returns_canonical_contract() -> None:
    validator = AsyncMock()
    validator.validate.return_value = ValidatedMediaUrl(
        platform=Platform.YOUTUBE,
        media_id="dQw4w9WgXcQ",
        canonical_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    )

    with TestClient(
        create_app(Settings(environment="test"), media_url_validator=validator)
    ) as client:
        response = client.post(
            "/api/media/validate",
            json={"url": "https://youtu.be/dQw4w9WgXcQ"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "valid": True,
        "platform": "youtube",
        "media_id": "dQw4w9WgXcQ",
        "canonical_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    }


def test_validate_endpoint_returns_stable_functional_error() -> None:
    validator = AsyncMock()
    validator.validate.side_effect = UrlValidationError("unsupported_platform")

    with TestClient(
        create_app(Settings(environment="test"), media_url_validator=validator)
    ) as client:
        response = client.post(
            "/api/media/validate",
            json={"url": "https://example.com/video"},
        )

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "unsupported_platform",
            "message": "Esta plataforma no está soportada en el MVP.",
        }
    }
