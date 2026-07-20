"""Endpoints for local-only application preferences."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.models.media import ValidationErrorDetail, ValidationErrorResponse
from app.models.settings import (
    DownloadDirectoryUpdateRequest,
    LocalSettingsResponse,
)
from app.system.download_directory import DownloadDirectoryError

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=LocalSettingsResponse)
async def get_settings(request: Request) -> LocalSettingsResponse | JSONResponse:
    service = request.app.state.local_settings_service
    if service is None:
        return _unavailable_response()
    settings = await service.get()
    return LocalSettingsResponse(
        download_output_root=str(settings.download_output_root)
    )


@router.put("/download-directory", response_model=LocalSettingsResponse)
async def update_download_directory(
    payload: DownloadDirectoryUpdateRequest, request: Request
) -> LocalSettingsResponse | JSONResponse:
    service = request.app.state.local_settings_service
    if service is None:
        return _unavailable_response()
    try:
        settings = await service.update_download_output_root(payload.path)
    except DownloadDirectoryError as error:
        response = ValidationErrorResponse(
            error=ValidationErrorDetail(code=error.code, message=error.message)
        )
        return JSONResponse(
            status_code=error.status_code, content=response.model_dump()
        )
    return LocalSettingsResponse(
        download_output_root=str(settings.download_output_root)
    )


def _unavailable_response() -> JSONResponse:
    response = ValidationErrorResponse(
        error=ValidationErrorDetail(
            code="settings_unavailable",
            message="La configuración local no está disponible.",
        )
    )
    return JSONResponse(status_code=503, content=response.model_dump())
