"""Media URL validation endpoints."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.media.validation import UrlValidationError
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
