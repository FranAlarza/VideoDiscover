import asyncio
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.downloader.domain import (
    AudioBitrate,
    DownloadFailure,
    DownloadSelection,
    DownloadStatus,
    DownloadTask,
    OutputType,
    VideoQuality,
)
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


def test_service_retries_failed_task_after_reinspection() -> None:
    async def scenario() -> None:
        validator, inspection = _dependencies()
        repository = InMemoryDownloadRepository()
        task = DownloadTask.create(
            platform=Platform.YOUTUBE,
            media_id="dQw4w9WgXcQ",
            title="Old title",
            canonical_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            selection=DownloadSelection(OutputType.VIDEO, VideoQuality.P720),
        )
        task.current_attempt.transition_to(DownloadStatus.DOWNLOADING)
        task.current_attempt.transition_to(
            DownloadStatus.FAILED,
            failure=DownloadFailure("network_error", "Connection failed"),
        )
        await repository.create(task)
        worker = Mock()
        service = DownloadTaskService(repository, validator, inspection, worker)

        retried = await service.retry(task.id)

        assert retried.status is DownloadStatus.QUEUED
        assert retried.queue_position == 1
        assert retried.title == "Example"
        assert [attempt.status for attempt in retried.attempts] == [
            DownloadStatus.FAILED,
            DownloadStatus.QUEUED,
        ]
        assert retried.current_attempt.number == 2
        validator.validate.assert_awaited_once_with(task.canonical_url)
        inspection.inspect_validated.assert_awaited_once()
        worker.notify.assert_called_once_with()

    asyncio.run(scenario())


def test_service_rejects_retry_from_completed_state() -> None:
    async def scenario() -> None:
        validator, inspection = _dependencies()
        repository = InMemoryDownloadRepository()
        service = DownloadTaskService(repository, validator, inspection)
        created = await service.create(
            DownloadCreateRequest(
                url="https://youtu.be/dQw4w9WgXcQ",
                output_type=OutputType.VIDEO,
                video_quality=VideoQuality.P720,
            )
        )

        with pytest.raises(DownloadApplicationError) as captured:
            await service.retry(created.id)

        assert captured.value.code == "retry_not_allowed"
        assert captured.value.status_code == 409

    asyncio.run(scenario())


def test_retry_does_not_create_attempt_when_format_disappeared() -> None:
    async def scenario() -> None:
        validator, inspection = _dependencies()
        inspection.inspect_validated.return_value.video_qualities = [1080]
        repository = InMemoryDownloadRepository()
        task = DownloadTask.create(
            platform=Platform.YOUTUBE,
            media_id="dQw4w9WgXcQ",
            title="Example",
            canonical_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            selection=DownloadSelection(OutputType.VIDEO, VideoQuality.P720),
        )
        task.current_attempt.transition_to(DownloadStatus.DOWNLOADING)
        task.current_attempt.transition_to(DownloadStatus.INTERRUPTED)
        await repository.create(task)
        service = DownloadTaskService(repository, validator, inspection)

        with pytest.raises(DownloadApplicationError) as captured:
            await service.retry(task.id)

        stored = await repository.get(task.id)
        assert captured.value.code == "format_unavailable"
        assert len(stored.attempts) == 1
        assert stored.status is DownloadStatus.INTERRUPTED

    asyncio.run(scenario())


def test_concurrent_retries_create_only_one_attempt() -> None:
    async def scenario() -> None:
        validator, inspection = _dependencies()
        repository = InMemoryDownloadRepository()
        task = DownloadTask.create(
            platform=Platform.YOUTUBE,
            media_id="dQw4w9WgXcQ",
            title="Example",
            canonical_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            selection=DownloadSelection(OutputType.VIDEO, VideoQuality.P720),
        )
        task.current_attempt.transition_to(DownloadStatus.DOWNLOADING)
        task.current_attempt.transition_to(DownloadStatus.INTERRUPTED)
        await repository.create(task)
        service = DownloadTaskService(repository, validator, inspection)

        results = await asyncio.gather(
            service.retry(task.id), service.retry(task.id), return_exceptions=True
        )

        assert sum(not isinstance(result, Exception) for result in results) == 1
        error = next(result for result in results if isinstance(result, Exception))
        assert isinstance(error, DownloadApplicationError)
        assert error.code == "retry_not_allowed"
        stored = await repository.get(task.id)
        assert stored is not None
        assert len(stored.attempts) == 2

    asyncio.run(scenario())
