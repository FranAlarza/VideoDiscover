"""Public media inspection contracts."""

from pydantic import BaseModel, ConfigDict, Field

from app.models.media import Platform


class MediaInspectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str


class MediaInspectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: Platform
    media_id: str
    title: str = Field(max_length=200)
    author: str | None = Field(default=None, max_length=200)
    duration_seconds: int | None = Field(default=None, ge=0)
    thumbnail_url: str | None = Field(default=None, max_length=2048)
    published_at: str | None = None
    estimated_size: int | None = Field(default=None, ge=0)
    video_qualities: list[int]
    audio_available: bool
    is_live: bool = False
