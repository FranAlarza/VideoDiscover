"""Public contracts for local application settings."""

from pydantic import BaseModel, ConfigDict, Field


class LocalSettingsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    download_output_root: str


class DownloadDirectoryUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1, max_length=4096)
