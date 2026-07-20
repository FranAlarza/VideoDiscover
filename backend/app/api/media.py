"""Media URL validation endpoints."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.media.inspection import MediaInspectionError
from app.media.validation import UrlValidationError
from app.models.inspection import MediaInspectionRequest, MediaInspectionResponse
from app.models.media import (
    MediaValidationRequest,
    ValidatedMediaUrl,
    ValidationErrorDetail,
    ValidationErrorResponse,
)

router = APIRouter(prefix="/api/media", tags=["media"])


@router.post(
    "/validate",
    response_model=ValidatedMediaUrl,
    responses={
        400: {"model": ValidationErrorResponse},
        503: {"model": ValidationErrorResponse},
    },
)
async def validate_media_url(
    payload: MediaValidationRequest, request: Request
) -> ValidatedMediaUrl | JSONResponse:
    """Validate and canonicalize one supported public media URL."""
    try:
        return await request.app.state.media_url_validator.validate(payload.url)
    except UrlValidationError as error:
        response = ValidationErrorResponse(
            error=ValidationErrorDetail(code=error.code, message=error.message)
        )
        return JSONResponse(
            status_code=error.status_code,
            content=response.model_dump(),
        )


@router.post(
    "/inspect",
    response_model=MediaInspectionResponse,
    responses={
        400: {"model": ValidationErrorResponse},
        404: {"model": ValidationErrorResponse},
        408: {"model": ValidationErrorResponse},
        429: {"model": ValidationErrorResponse},
        502: {"model": ValidationErrorResponse},
        503: {"model": ValidationErrorResponse},
    },
)
async def inspect_media(
    payload: MediaInspectionRequest, request: Request
) -> MediaInspectionResponse | JSONResponse:
    """Inspect one validated media URL without downloading its content."""
    try:
        return await request.app.state.media_inspection_service.inspect(payload.url)
    except (UrlValidationError, MediaInspectionError) as error:
        response = ValidationErrorResponse(
            error=ValidationErrorDetail(code=error.code, message=error.message)
        )
        return JSONResponse(
            status_code=error.status_code,
            content=response.model_dump(),
        )
