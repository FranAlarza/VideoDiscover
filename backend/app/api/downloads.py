"""Download task endpoints; execution is introduced in the next delivery."""

from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.downloader.service import DownloadApplicationError
from app.media.inspection import MediaInspectionError
from app.media.validation import UrlValidationError
from app.models.downloads import (
    DownloadCreateRequest,
    DownloadListResponse,
    DownloadTaskResponse,
)
from app.models.media import ValidationErrorDetail, ValidationErrorResponse

router = APIRouter(prefix="/api/downloads", tags=["downloads"])


@router.post("", response_model=DownloadTaskResponse, status_code=201)
async def create_download(
    payload: DownloadCreateRequest, request: Request
) -> DownloadTaskResponse | JSONResponse:
    try:
        return await request.app.state.download_task_service.create(payload)
    except (
        UrlValidationError,
        MediaInspectionError,
        DownloadApplicationError,
    ) as error:
        return _error_response(error)


@router.get("", response_model=DownloadListResponse)
async def list_downloads(request: Request) -> DownloadListResponse:
    return await request.app.state.download_task_service.list()


@router.get("/{task_id}", response_model=DownloadTaskResponse)
async def get_download(
    task_id: UUID, request: Request
) -> DownloadTaskResponse | JSONResponse:
    try:
        return await request.app.state.download_task_service.get(task_id)
    except DownloadApplicationError as error:
        return _error_response(error)


@router.post("/{task_id}/cancel", response_model=DownloadTaskResponse)
async def cancel_download(
    task_id: UUID, request: Request
) -> DownloadTaskResponse | JSONResponse:
    try:
        return await request.app.state.download_task_service.cancel(task_id)
    except DownloadApplicationError as error:
        return _error_response(error)


@router.post("/{task_id}/retry", response_model=DownloadTaskResponse)
async def retry_download(
    task_id: UUID, request: Request
) -> DownloadTaskResponse | JSONResponse:
    try:
        return await request.app.state.download_task_service.retry(task_id)
    except (
        UrlValidationError,
        MediaInspectionError,
        DownloadApplicationError,
    ) as error:
        return _error_response(error)


def _error_response(
    error: UrlValidationError | MediaInspectionError | DownloadApplicationError,
) -> JSONResponse:
    response = ValidationErrorResponse(
        error=ValidationErrorDetail(code=error.code, message=error.message)
    )
    return JSONResponse(status_code=error.status_code, content=response.model_dump())
