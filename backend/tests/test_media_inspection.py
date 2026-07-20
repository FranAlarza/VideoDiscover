import asyncio
import threading
import time
from multiprocessing.connection import Connection
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.media.inspection import (
    MediaInspectionError,
    MediaInspectionService,
    ProcessInspectionRunner,
    RawInspectionError,
    _build_yt_dlp_options,
    _classify_yt_dlp_error,
    _limit_ipc_metadata,
)
from app.media.validation import NetworkSafetyChecker
from app.models.inspection import MediaInspectionResponse
from app.models.media import Platform, ValidatedMediaUrl


class StubRunner:
    def __init__(self, result: dict[str, Any] | Exception) -> None:
        self.result = result
        self.calls: list[tuple[str, str, float]] = []

    def inspect(
        self, canonical_url: str, node_binary: str, timeout_seconds: float
    ) -> dict[str, Any]:
        self.calls.append((canonical_url, node_binary, timeout_seconds))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _blocking_worker(
    _connection: Connection, _canonical_url: str, _node_binary: str
) -> None:
    time.sleep(10)


def _public_thumbnail_checker() -> NetworkSafetyChecker:
    async def resolver(_hostname: str, _port: int) -> list[str]:
        return ["8.8.8.8"]

    return NetworkSafetyChecker(resolver)


def _validated(platform: Platform = Platform.YOUTUBE) -> ValidatedMediaUrl:
    if platform is Platform.TIKTOK:
        return ValidatedMediaUrl(
            platform=platform,
            media_id="6718335390845095173",
            canonical_url=(
                "https://www.tiktok.com/@scout2015/video/6718335390845095173"
            ),
        )
    return ValidatedMediaUrl(
        platform=platform,
        media_id="dQw4w9WgXcQ",
        canonical_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    )


def test_inspection_uses_only_validated_canonical_url_and_maps_formats() -> None:
    validator = AsyncMock()
    validator.validate.return_value = _validated()
    runner = StubRunner(
        {
            "title": "  Example   video  ",
            "uploader": "Creator",
            "duration": 123.8,
            "thumbnail": "https://img.youtube.com/example.jpg",
            "upload_date": "20260720",
            "formats": [
                {
                    "width": 1920,
                    "height": 1080,
                    "vcodec": "avc1",
                    "acodec": "none",
                    "filesize": 10_000,
                    "url": "https://signed.example/secret-token",
                },
                {
                    "width": 1920,
                    "height": 1080,
                    "vcodec": "vp9",
                    "acodec": "none",
                    "filesize_approx": 9_000,
                },
                {
                    "width": 1280,
                    "height": 720,
                    "vcodec": "avc1",
                    "acodec": "aac",
                    "filesize": 8_000,
                },
                {"vcodec": "none", "acodec": "opus", "filesize": 2_000},
            ],
        }
    )
    service = MediaInspectionService(
        validator,
        runner=runner,
        node_binary="/tools/node",
        timeout_seconds=12,
        thumbnail_checker=_public_thumbnail_checker(),
    )

    result = asyncio.run(service.inspect("https://untrusted.example/input"))

    assert result == MediaInspectionResponse(
        platform=Platform.YOUTUBE,
        media_id="dQw4w9WgXcQ",
        title="Example video",
        author="Creator",
        duration_seconds=123,
        thumbnail_url="https://img.youtube.com/example.jpg",
        published_at="2026-07-20",
        estimated_size=10_000,
        video_qualities=[1080, 720],
        audio_available=True,
        is_live=False,
    )
    assert runner.calls == [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "/tools/node", 12)
    ]
    assert "secret-token" not in result.model_dump_json()


def test_inspection_allows_missing_optional_tiktok_metadata() -> None:
    validator = AsyncMock()
    validator.validate.return_value = _validated(Platform.TIKTOK)
    runner = StubRunner({"title": "TikTok", "formats": []})
    service = MediaInspectionService(
        validator, runner=runner, node_binary="/tools/node"
    )

    result = asyncio.run(service.inspect("https://www.tiktok.com/video"))

    assert result.platform is Platform.TIKTOK
    assert result.author is None
    assert result.duration_seconds is None
    assert result.thumbnail_url is None
    assert result.video_qualities == []
    assert result.audio_available is False


def test_inspection_maps_vertical_video_to_supported_quality() -> None:
    validator = AsyncMock()
    validator.validate.return_value = _validated(Platform.TIKTOK)
    runner = StubRunner(
        {
            "title": "Vertical TikTok",
            "formats": [
                {
                    "width": 576,
                    "height": 1024,
                    "vcodec": "h264",
                    "acodec": "aac",
                }
            ],
        }
    )
    service = MediaInspectionService(
        validator, runner=runner, node_binary="/tools/node"
    )

    result = asyncio.run(service.inspect("https://www.tiktok.com/video"))

    assert result.video_qualities == [480]


def test_inspection_discards_thumbnail_with_private_destination() -> None:
    async def private_resolver(_hostname: str, _port: int) -> list[str]:
        return ["127.0.0.1"]

    validator = AsyncMock()
    validator.validate.return_value = _validated()
    service = MediaInspectionService(
        validator,
        runner=StubRunner(
            {
                "title": "Example",
                "thumbnail": "https://thumbnail.example/image.jpg?token=secret",
            }
        ),
        node_binary="/tools/node",
        thumbnail_checker=NetworkSafetyChecker(private_resolver),
    )

    result = asyncio.run(service.inspect("https://youtube.example/video"))

    assert result.thumbnail_url is None


def test_ipc_metadata_is_bounded_and_drops_sensitive_fields() -> None:
    result = _limit_ipc_metadata(
        {
            "id": "video-id",
            "title": "x" * 5_000,
            "http_headers": {"Authorization": "secret"},
            "cookies": "session=secret",
            "url": "https://media.example/video?token=secret",
            "entries": [{"url": "secret"}],
            "formats": [
                {
                    "height": 1080,
                    "width": 1920,
                    "vcodec": "h264",
                    "url": "https://signed.example/secret",
                    "http_headers": {"Cookie": "secret"},
                }
            ],
        }
    )

    assert result["id"] == "video-id"
    assert len(result["title"]) == 2048
    assert result["entries"] is True
    assert result["formats"] == [{"height": 1080, "width": 1920, "vcodec": "h264"}]
    serialized = repr(result)
    assert "Authorization" not in serialized
    assert "Cookie" not in serialized
    assert "signed.example" not in serialized
    assert "token=secret" not in serialized


def test_metadata_discards_invalid_date_duration_and_size() -> None:
    validator = AsyncMock()
    validator.validate.return_value = _validated()
    service = MediaInspectionService(
        validator,
        runner=StubRunner(
            {
                "id": "dQw4w9WgXcQ",
                "title": "Example",
                "duration": 999_999_999,
                "upload_date": "20261340",
                "formats": [{"filesize": 999_999_999_999_999}],
            }
        ),
        node_binary="/tools/node",
    )

    result = asyncio.run(service.inspect("https://youtube.example/video"))

    assert result.duration_seconds is None
    assert result.published_at is None
    assert result.estimated_size is None


def test_metadata_rejects_extractor_id_mismatch() -> None:
    validator = AsyncMock()
    validator.validate.return_value = _validated()
    service = MediaInspectionService(
        validator,
        runner=StubRunner({"id": "different-id", "title": "Example"}),
        node_binary="/tools/node",
    )

    with pytest.raises(MediaInspectionError) as captured:
        asyncio.run(service.inspect("https://youtube.example/video"))

    assert captured.value.code == "unknown_error"


def test_process_runner_terminates_worker_after_timeout() -> None:
    runner = ProcessInspectionRunner(worker_target=_blocking_worker)

    with pytest.raises(MediaInspectionError) as captured:
        runner.inspect("https://example.test/video", "/tools/node", 0.05)

    assert captured.value.code == "inspection_timeout"
    assert runner.active_process_count == 0


def test_inspection_serializes_concurrent_requests() -> None:
    class ConcurrencyRunner(StubRunner):
        def __init__(self) -> None:
            super().__init__({"title": "Example", "formats": []})
            self.active = 0
            self.maximum_active = 0
            self.lock = threading.Lock()

        def inspect(
            self, canonical_url: str, node_binary: str, timeout_seconds: float
        ) -> dict[str, Any]:
            with self.lock:
                self.active += 1
                self.maximum_active = max(self.maximum_active, self.active)
            time.sleep(0.05)
            with self.lock:
                self.active -= 1
            return super().inspect(canonical_url, node_binary, timeout_seconds)

    validator = AsyncMock()
    validator.validate.return_value = _validated()
    runner = ConcurrencyRunner()
    service = MediaInspectionService(
        validator,
        runner=runner,
        node_binary="/tools/node",
        maximum_concurrency=1,
    )

    async def run_concurrently() -> None:
        await asyncio.gather(
            service.inspect("https://example.test/one"),
            service.inspect("https://example.test/two"),
        )

    asyncio.run(run_concurrently())

    assert runner.maximum_active == 1


@pytest.mark.parametrize(
    ("raw_info", "expected_code"),
    [
        ({"_type": "playlist", "title": "List"}, "playlist_not_supported"),
        ({"title": "List", "entries": [{"id": "one"}]}, "playlist_not_supported"),
        ({"title": "Live", "is_live": True}, "media_unavailable"),
        ({"formats": []}, "unknown_error"),
    ],
)
def test_inspection_rejects_unsupported_or_malformed_results(
    raw_info: dict[str, Any], expected_code: str
) -> None:
    validator = AsyncMock()
    validator.validate.return_value = _validated()
    service = MediaInspectionService(
        validator,
        runner=StubRunner(raw_info),
        node_binary="/tools/node",
    )

    with pytest.raises(MediaInspectionError) as captured:
        asyncio.run(service.inspect("https://youtube.example/video"))

    assert captured.value.code == expected_code


def test_inspection_preserves_real_timeout_error() -> None:
    validator = AsyncMock()
    validator.validate.return_value = _validated()
    service = MediaInspectionService(
        validator,
        runner=StubRunner(MediaInspectionError("inspection_timeout", status_code=408)),
        node_binary="/tools/node",
    )

    with pytest.raises(MediaInspectionError) as captured:
        asyncio.run(service.inspect("https://youtube.example/video"))

    assert captured.value.code == "inspection_timeout"
    assert captured.value.status_code == 408


@pytest.mark.parametrize(
    ("message", "code", "status"),
    [
        ("This is a private video. Sign in", "private_media", 400),
        ("Video unavailable: removed", "media_unavailable", 404),
        ("Not available in your country", "region_restricted", 400),
        ("This video is age-restricted", "age_restricted", 400),
        (
            "This post may not be comfortable for some audiences. Log in for access.",
            "age_restricted",
            400,
        ),
        ("DRM protected content", "drm_protected", 400),
        ("Playlist result", "playlist_not_supported", 400),
        ("HTTP Error 429: Too Many Requests", "temporarily_blocked", 429),
        ("Network connection timed out", "network_error", 503),
        ("Unexpected extractor response", "unknown_error", 502),
    ],
)
def test_yt_dlp_errors_are_translated(message: str, code: str, status: int) -> None:
    result = _classify_yt_dlp_error(message)

    assert result.code == code
    assert result.status_code == status


def test_runner_error_is_translated_without_exposing_raw_message() -> None:
    validator = AsyncMock()
    validator.validate.return_value = _validated()
    service = MediaInspectionService(
        validator,
        runner=StubRunner(RawInspectionError("private video token=secret")),
        node_binary="/tools/node",
    )

    with pytest.raises(MediaInspectionError) as captured:
        asyncio.run(service.inspect("https://youtube.example/video"))

    assert captured.value.code == "private_media"
    assert "secret" not in captured.value.message


def test_yt_dlp_options_never_download_and_use_explicit_node() -> None:
    options = _build_yt_dlp_options("/tools/node24")

    assert options["skip_download"] is True
    assert options["simulate"] is True
    assert options["noplaylist"] is True
    assert options["js_runtimes"] == {"node": {"path": "/tools/node24"}}
    assert options["remote_components"] == set()
    assert options["logger"].__class__.__name__ == "_QuietYtDlpLogger"


def test_inspect_endpoint_returns_public_contract() -> None:
    inspection_service = AsyncMock()
    inspection_service.inspect.return_value = MediaInspectionResponse(
        platform=Platform.YOUTUBE,
        media_id="dQw4w9WgXcQ",
        title="Example",
        video_qualities=[1080, 720],
        audio_available=True,
    )

    with TestClient(
        create_app(
            Settings(environment="test"),
            media_inspection_service=inspection_service,
        )
    ) as client:
        response = client.post(
            "/api/media/inspect",
            json={"url": "https://youtu.be/dQw4w9WgXcQ"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "platform": "youtube",
        "media_id": "dQw4w9WgXcQ",
        "title": "Example",
        "author": None,
        "duration_seconds": None,
        "thumbnail_url": None,
        "published_at": None,
        "estimated_size": None,
        "video_qualities": [1080, 720],
        "audio_available": True,
        "is_live": False,
    }
    inspection_service.shutdown.assert_awaited_once_with()


def test_inspect_endpoint_returns_sanitized_error() -> None:
    inspection_service = AsyncMock()
    inspection_service.inspect.side_effect = MediaInspectionError(
        "private_media", status_code=400
    )

    with TestClient(
        create_app(
            Settings(environment="test"),
            media_inspection_service=inspection_service,
        )
    ) as client:
        response = client.post(
            "/api/media/inspect",
            json={"url": "https://youtu.be/dQw4w9WgXcQ"},
        )

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "private_media",
            "message": "Este contenido es privado o requiere iniciar sesión.",
        }
    }
