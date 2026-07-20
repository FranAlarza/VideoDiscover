"""Public download task API contracts."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.downloader.domain import (
    AudioBitrate,
    DownloadStatus,
    OutputType,
    VideoQuality,
)
from app.models.media import Platform


class DownloadCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    output_type: OutputType
    video_quality: VideoQuality | None = None
    audio_bitrate: AudioBitrate | None = None

    @model_validator(mode="after")
    def validate_selection(self) -> "DownloadCreateRequest":
        if self.output_type is OutputType.VIDEO:
            if self.video_quality is None or self.audio_bitrate is not None:
                raise ValueError(
                    "video output requires video_quality and forbids audio_bitrate"
                )
        elif self.audio_bitrate is None or self.video_quality is not None:
            raise ValueError(
                "audio output requires audio_bitrate and forbids video_quality"
            )
        return self


class DownloadSelectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_type: OutputType
    video_quality: VideoQuality | None
    audio_bitrate: AudioBitrate | None


class DownloadProgressResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    percentage: float | None
    downloaded_bytes: int | None
    total_bytes: int | None
    speed_bytes_per_second: float | None
    eta_seconds: int | None


class DownloadFailureResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str


class DownloadResultResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str
    extension: str
    size_bytes: int = Field(ge=0)
    effective_quality: int | None


class DownloadAttemptResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: int = Field(ge=1)
    status: DownloadStatus
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    progress: DownloadProgressResponse
    failure: DownloadFailureResponse | None
    result: DownloadResultResponse | None


class DownloadTaskResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    platform: Platform
    media_id: str
    title: str
    selection: DownloadSelectionResponse
    status: DownloadStatus
    queue_position: int | None = Field(default=None, ge=1)
    created_at: datetime
    current_attempt: DownloadAttemptResponse


class DownloadListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[DownloadTaskResponse]
