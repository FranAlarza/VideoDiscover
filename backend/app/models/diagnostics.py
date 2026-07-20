"""Models exposed by the local dependency diagnostics endpoint."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class DependencyName(StrEnum):
    """External components required by the downloader."""

    YT_DLP = "yt-dlp"
    NODE = "node"
    FFMPEG = "ffmpeg"
    FFPROBE = "ffprobe"


class DependencyStatus(StrEnum):
    """Compatibility state of one dependency."""

    AVAILABLE = "available"
    MISSING = "missing"
    INCOMPATIBLE = "incompatible"


class DependencyDiagnostic(BaseModel):
    """Sanitized dependency result safe to return to the local frontend."""

    model_config = ConfigDict(extra="forbid")

    name: DependencyName
    status: DependencyStatus
    version: str | None = None
    error_code: str | None = None


class SystemDiagnostics(BaseModel):
    """Snapshot produced once when the API starts."""

    model_config = ConfigDict(extra="forbid")

    ready: bool
    dependencies: list[DependencyDiagnostic]
