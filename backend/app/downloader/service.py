"""Application service for download task creation and queries."""

import asyncio
from uuid import UUID

from app.downloader.domain import (
    DownloadAttempt,
    DownloadResult,
    DownloadSelection,
    DownloadStatus,
    DownloadTask,
    VideoQuality,
)
from app.downloader.repository import DownloadRepository
from app.downloader.worker import DownloadWorker
from app.events.broker import DownloadEventBroker
from app.media.inspection import MediaInspectionService
from app.media.validation import MediaUrlValidationService
from app.models.downloads import (
    DownloadAttemptResponse,
    DownloadCreateRequest,
    DownloadFailureResponse,
    DownloadListResponse,
    DownloadProgressResponse,
    DownloadResultResponse,
    DownloadSelectionResponse,
    DownloadTaskResponse,
)


class DownloadApplicationError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class DownloadTaskService:
    def __init__(
        self,
        repository: DownloadRepository,
        validator: MediaUrlValidationService,
        inspection_service: MediaInspectionService,
        worker: DownloadWorker | None = None,
        event_broker: DownloadEventBroker | None = None,
    ) -> None:
        self._repository = repository
        self._validator = validator
        self._inspection_service = inspection_service
        self._worker = worker
        self._event_broker = event_broker
        self._retry_lock = asyncio.Lock()

    async def create(self, request: DownloadCreateRequest) -> DownloadTaskResponse:
        validated = await self._validator.validate(request.url)
        inspection = await self._inspection_service.inspect_validated(validated)

        _ensure_format_available(
            request.video_quality,
            inspection.video_qualities,
            inspection.audio_available,
        )

        selection = DownloadSelection(
            output_type=request.output_type,
            video_quality=request.video_quality,
            audio_bitrate=request.audio_bitrate,
        )
        task = DownloadTask.create(
            platform=validated.platform,
            media_id=validated.media_id,
            title=inspection.title,
            canonical_url=validated.canonical_url,
            selection=selection,
        )
        created = await self._repository.create(task)
        tasks = await self._repository.list()
        queue_position = _queue_position(created, tasks)
        await self._publish(
            created, name="download.created", queue_position=queue_position
        )
        if self._worker is not None:
            self._worker.notify()
        return _to_response(created, queue_position)

    async def get(self, task_id: UUID) -> DownloadTaskResponse:
        task = await self._repository.get(task_id)
        if task is None:
            raise _not_found()
        tasks = await self._repository.list()
        return _to_response(task, _queue_position(task, tasks))

    async def list(self) -> DownloadListResponse:
        tasks = await self._repository.list()
        return DownloadListResponse(
            items=[_to_response(task, _queue_position(task, tasks)) for task in tasks]
        )

    async def cancel(self, task_id: UUID) -> DownloadTaskResponse:
        task = await self._repository.get(task_id)
        if task is None:
            raise _not_found()
        if task.status is DownloadStatus.QUEUED:
            task.current_attempt.transition_to(DownloadStatus.CANCELLED)
            saved = await self._repository.save(task)
            await self._publish(saved, force=True)
            return _to_response(saved, None)
        if (
            task.status in {DownloadStatus.DOWNLOADING, DownloadStatus.PROCESSING}
            and self._worker is not None
            and self._worker.request_cancel(task_id)
        ):
            return _to_response(task, None)
        if task.status is not DownloadStatus.QUEUED:
            raise DownloadApplicationError(
                "cancellation_not_allowed",
                "Esta descarga ya no puede cancelarse desde la cola.",
                status_code=409,
            )
        raise AssertionError("unreachable")

    async def retry(self, task_id: UUID) -> DownloadTaskResponse:
        async with self._retry_lock:
            task = await self._repository.get(task_id)
            if task is None:
                raise _not_found()
            if task.status not in {
                DownloadStatus.FAILED,
                DownloadStatus.INTERRUPTED,
            }:
                raise DownloadApplicationError(
                    "retry_not_allowed",
                    "Solo se pueden reintentar descargas fallidas o interrumpidas.",
                    status_code=409,
                )

            validated = await self._validator.validate(task.canonical_url)
            inspection = await self._inspection_service.inspect_validated(validated)
            _ensure_format_available(
                task.selection.video_quality,
                inspection.video_qualities,
                inspection.audio_available,
            )
            task.canonical_url = validated.canonical_url
            task.title = inspection.title
            task.start_new_attempt()
            saved = await self._repository.save(task)
        await self._publish(saved, force=True)
        if self._worker is not None:
            self._worker.notify()
        tasks = await self._repository.list()
        return _to_response(saved, _queue_position(saved, tasks))

    async def delete(self, task_id: UUID) -> None:
        task = await self._repository.get(task_id)
        if task is None:
            raise _not_found()
        if task.status in {
            DownloadStatus.QUEUED,
            DownloadStatus.DOWNLOADING,
            DownloadStatus.PROCESSING,
        }:
            raise DownloadApplicationError(
                "deletion_not_allowed",
                "Solo se pueden eliminar descargas que ya hayan terminado.",
                status_code=409,
            )
        await self._repository.delete(task_id)
        await self._publish(task, name="download.deleted", force=True)

    async def get_file_result(self, task_id: UUID) -> DownloadResult:
        task = await self._repository.get(task_id)
        if task is None:
            raise _not_found()
        result = task.current_attempt.result
        if task.status is not DownloadStatus.COMPLETED or result is None:
            raise DownloadApplicationError(
                "download_file_not_ready",
                "La descarga todavía no tiene un archivo final disponible.",
                status_code=409,
            )
        return result

    async def _publish(
        self,
        task: DownloadTask,
        *,
        name: str = "download.updated",
        queue_position: int | None = None,
        force: bool = False,
    ) -> None:
        if self._event_broker is not None:
            await self._event_broker.publish(
                task,
                name=name,
                queue_position=queue_position,
                force=force,
            )


def _not_found() -> DownloadApplicationError:
    return DownloadApplicationError(
        "download_not_found",
        "No se ha encontrado la descarga solicitada.",
        status_code=404,
    )


def _ensure_format_available(
    video_quality: VideoQuality | None,
    available_video_qualities: list[int],
    audio_available: bool,
) -> None:
    if video_quality is not None:
        if video_quality.value not in available_video_qualities:
            raise DownloadApplicationError(
                "format_unavailable",
                "La calidad seleccionada ya no está disponible.",
                status_code=400,
            )
    elif not audio_available:
        raise DownloadApplicationError(
            "format_unavailable",
            "Este contenido no ofrece una pista de audio disponible.",
            status_code=400,
        )


def _queue_position(task: DownloadTask, tasks: list[DownloadTask]) -> int | None:
    if task.status is not DownloadStatus.QUEUED:
        return None
    queued = [item for item in tasks if item.status is DownloadStatus.QUEUED]
    return next(
        (
            position
            for position, item in enumerate(queued, start=1)
            if item.id == task.id
        ),
        None,
    )


def _to_response(
    task: DownloadTask, queue_position: int | None
) -> DownloadTaskResponse:
    attempts = [_attempt_to_response(attempt) for attempt in task.attempts]
    return DownloadTaskResponse(
        id=task.id,
        platform=task.platform,
        media_id=task.media_id,
        title=task.title,
        selection=DownloadSelectionResponse(
            output_type=task.selection.output_type,
            video_quality=task.selection.video_quality,
            audio_bitrate=task.selection.audio_bitrate,
        ),
        status=task.status,
        queue_position=queue_position,
        created_at=task.created_at,
        current_attempt=attempts[-1],
        attempts=attempts,
    )


def _attempt_to_response(attempt: DownloadAttempt) -> DownloadAttemptResponse:
    return DownloadAttemptResponse(
        number=attempt.number,
        status=attempt.status,
        created_at=attempt.created_at,
        started_at=attempt.started_at,
        finished_at=attempt.finished_at,
        progress=DownloadProgressResponse(
            percentage=attempt.progress.percentage,
            downloaded_bytes=attempt.progress.downloaded_bytes,
            total_bytes=attempt.progress.total_bytes,
            speed_bytes_per_second=attempt.progress.speed_bytes_per_second,
            eta_seconds=attempt.progress.eta_seconds,
        ),
        failure=(
            DownloadFailureResponse(
                code=attempt.failure.code,
                message=attempt.failure.message,
            )
            if attempt.failure
            else None
        ),
        result=(
            DownloadResultResponse(
                filename=attempt.result.filename,
                extension=attempt.result.extension,
                size_bytes=attempt.result.size_bytes,
                effective_quality=attempt.result.effective_quality,
            )
            if attempt.result
            else None
        ),
    )
