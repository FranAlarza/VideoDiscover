import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.downloader.domain import AudioBitrate, DownloadStatus, OutputType, VideoQuality
from app.downloader.repository import InMemoryDownloadRepository
from app.downloader.service import DownloadApplicationError, DownloadTaskService
from app.models.downloads import DownloadCreateRequest
from app.models.inspection import MediaInspectionResponse
from app.models.media import Platform, ValidatedMediaUrl


def _dependencies() -> tuple[AsyncMock, AsyncMock]:
    validator = AsyncMock()
    validator.validate.return_value = ValidatedMediaUrl(
        platform=Platform.YOUTUBE,
        media_id="dQw4w9WgXcQ",
        canonical_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    )
    inspection = AsyncMock()
    inspection.inspect_validated.return_value = MediaInspectionResponse(
        platform=Platform.YOUTUBE,
        media_id="dQw4w9WgXcQ",
        title="Example",
        video_qualities=[1080, 720],
        audio_available=True,
    )
    return validator, inspection


def test_service_creates_lists_gets_and_cancels_video_task() -> None:
    async def scenario() -> None:
        validator, inspection = _dependencies()
        service = DownloadTaskService(
            InMemoryDownloadRepository(), validator, inspection
        )
        request = DownloadCreateRequest(
            url="https://youtu.be/dQw4w9WgXcQ",
            output_type=OutputType.VIDEO,
            video_quality=VideoQuality.P1080,
        )

        created = await service.create(request)
        fetched = await service.get(created.id)
        listed = await service.list()
        cancelled = await service.cancel(created.id)

        assert created.status is DownloadStatus.QUEUED
        assert created.queue_position == 1
        assert created.selection.video_quality is VideoQuality.P1080
        assert fetched.id == created.id
        assert [item.id for item in listed.items] == [created.id]
        assert cancelled.status is DownloadStatus.CANCELLED
        assert cancelled.queue_position is None
        validator.validate.assert_awaited_once_with(request.url)
        inspection.inspect_validated.assert_awaited_once()

    asyncio.run(scenario())


def test_service_creates_audio_task() -> None:
    async def scenario() -> None:
        validator, inspection = _dependencies()
        service = DownloadTaskService(
            InMemoryDownloadRepository(), validator, inspection
        )

        created = await service.create(
            DownloadCreateRequest(
                url="https://youtu.be/dQw4w9WgXcQ",
                output_type=OutputType.AUDIO,
                audio_bitrate=AudioBitrate.KBPS192,
            )
        )

        assert created.selection.audio_bitrate is AudioBitrate.KBPS192

    asyncio.run(scenario())


def test_service_rejects_unavailable_quality() -> None:
    async def scenario() -> None:
        validator, inspection = _dependencies()
        service = DownloadTaskService(
            InMemoryDownloadRepository(), validator, inspection
        )

        with pytest.raises(DownloadApplicationError) as captured:
            await service.create(
                DownloadCreateRequest(
                    url="https://youtu.be/dQw4w9WgXcQ",
                    output_type=OutputType.VIDEO,
                    video_quality=VideoQuality.P2160,
                )
            )
        assert captured.value.code == "format_unavailable"

    asyncio.run(scenario())


def test_service_returns_not_found() -> None:
    async def scenario() -> None:
        validator, inspection = _dependencies()
        service = DownloadTaskService(
            InMemoryDownloadRepository(), validator, inspection
        )

        with pytest.raises(DownloadApplicationError) as captured:
            await service.get(uuid4())
        assert captured.value.code == "download_not_found"
        assert captured.value.status_code == 404

    asyncio.run(scenario())
