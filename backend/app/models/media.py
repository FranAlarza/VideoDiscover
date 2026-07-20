"""Media URL validation contracts."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class Platform(StrEnum):
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"


class MediaValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str


class ValidatedMediaUrl(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool = True
    platform: Platform
    media_id: str
    canonical_url: str


class ValidationErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str


class ValidationErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ValidationErrorDetail
