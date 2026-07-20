"""Application service for download task creation and queries."""

from uuid import UUID

from app.downloader.domain import (
    DownloadSelection,
    DownloadStatus,
    DownloadTask,
)
from app.downloader.repository import DownloadRepository
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
    ) -> None:
        self._repository = repository
        self._validator = validator
        self._inspection_service = inspection_service

    async def create(self, request: DownloadCreateRequest) -> DownloadTaskResponse:
        validated = await self._validator.validate(request.url)
        inspection = await self._inspection_service.inspect_validated(validated)

        if request.video_quality is not None:
            if request.video_quality.value not in inspection.video_qualities:
                raise DownloadApplicationError(
                    "format_unavailable",
                    "La calidad seleccionada ya no está disponible.",
                    status_code=400,
                )
        elif not inspection.audio_available:
            raise DownloadApplicationError(
                "format_unavailable",
                "Este contenido no ofrece una pista de audio disponible.",
                status_code=400,
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
        return _to_response(created, _queue_position(created, tasks))

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
        if task.status is not DownloadStatus.QUEUED:
            raise DownloadApplicationError(
                "cancellation_not_allowed",
                "Esta descarga ya no puede cancelarse desde la cola.",
                status_code=409,
            )
        task.current_attempt.transition_to(DownloadStatus.CANCELLED)
        saved = await self._repository.save(task)
        return _to_response(saved, None)


def _not_found() -> DownloadApplicationError:
    return DownloadApplicationError(
        "download_not_found",
        "No se ha encontrado la descarga solicitada.",
        status_code=404,
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
    attempt = task.current_attempt
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
        current_attempt=DownloadAttemptResponse(
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
        ),
    )
