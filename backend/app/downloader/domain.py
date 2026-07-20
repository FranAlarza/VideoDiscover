"""Download task aggregate and state machine."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import IntEnum, StrEnum
from pathlib import Path
from uuid import UUID, uuid4

from app.models.media import Platform


class DownloadStatus(StrEnum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


class OutputType(StrEnum):
    VIDEO = "video"
    AUDIO = "audio"


class VideoQuality(IntEnum):
    P360 = 360
    P480 = 480
    P720 = 720
    P1080 = 1080
    P1440 = 1440
    P2160 = 2160


class AudioBitrate(IntEnum):
    KBPS128 = 128
    KBPS192 = 192
    KBPS320 = 320


class DownloadDomainError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class DownloadSelection:
    output_type: OutputType
    video_quality: VideoQuality | None = None
    audio_bitrate: AudioBitrate | None = None

    def __post_init__(self) -> None:
        if self.output_type is OutputType.VIDEO:
            if self.video_quality is None or self.audio_bitrate is not None:
                raise DownloadDomainError(
                    "invalid_download_options",
                    (
                        "Una descarga de vídeo requiere calidad y no admite "
                        "bitrate de audio."
                    ),
                )
        elif self.audio_bitrate is None or self.video_quality is not None:
            raise DownloadDomainError(
                "invalid_download_options",
                "Una descarga de audio requiere bitrate y no admite calidad de vídeo.",
            )


@dataclass(frozen=True, slots=True)
class DownloadProgress:
    percentage: float | None = None
    downloaded_bytes: int | None = None
    total_bytes: int | None = None
    speed_bytes_per_second: float | None = None
    eta_seconds: int | None = None

    def __post_init__(self) -> None:
        if self.percentage is not None and not 0 <= self.percentage <= 100:
            raise DownloadDomainError("invalid_progress", "El porcentaje no es válido.")
        numeric_values = (
            self.downloaded_bytes,
            self.total_bytes,
            self.speed_bytes_per_second,
            self.eta_seconds,
        )
        if any(value is not None and value < 0 for value in numeric_values):
            raise DownloadDomainError("invalid_progress", "El progreso no es válido.")


@dataclass(frozen=True, slots=True)
class DownloadFailure:
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class DownloadResult:
    filename: str
    extension: str
    size_bytes: int
    effective_quality: int | None = None
    output_directory: str | None = None

    def __post_init__(self) -> None:
        if not self.filename or "/" in self.filename or "\\" in self.filename:
            raise DownloadDomainError("invalid_result", "El nombre final no es válido.")
        if self.size_bytes < 0:
            raise DownloadDomainError("invalid_result", "El tamaño final no es válido.")
        if self.output_directory is not None:
            directory = Path(self.output_directory)
            if not directory.is_absolute() or "\x00" in self.output_directory:
                raise DownloadDomainError(
                    "invalid_result", "La carpeta final no es válida."
                )


_ALLOWED_TRANSITIONS: dict[DownloadStatus, set[DownloadStatus]] = {
    DownloadStatus.QUEUED: {DownloadStatus.DOWNLOADING, DownloadStatus.CANCELLED},
    DownloadStatus.DOWNLOADING: {
        DownloadStatus.PROCESSING,
        DownloadStatus.COMPLETED,
        DownloadStatus.FAILED,
        DownloadStatus.CANCELLED,
        DownloadStatus.INTERRUPTED,
    },
    DownloadStatus.PROCESSING: {
        DownloadStatus.COMPLETED,
        DownloadStatus.FAILED,
        DownloadStatus.CANCELLED,
        DownloadStatus.INTERRUPTED,
    },
}
_TERMINAL_STATUSES = {
    DownloadStatus.COMPLETED,
    DownloadStatus.FAILED,
    DownloadStatus.CANCELLED,
    DownloadStatus.INTERRUPTED,
}


@dataclass(slots=True)
class DownloadAttempt:
    number: int
    status: DownloadStatus = DownloadStatus.QUEUED
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    finished_at: datetime | None = None
    progress: DownloadProgress = field(default_factory=DownloadProgress)
    failure: DownloadFailure | None = None
    result: DownloadResult | None = None

    def transition_to(
        self,
        new_status: DownloadStatus,
        *,
        failure: DownloadFailure | None = None,
        result: DownloadResult | None = None,
    ) -> None:
        if new_status not in _ALLOWED_TRANSITIONS.get(self.status, set()):
            raise DownloadDomainError(
                "invalid_status_transition",
                f"No se puede pasar de {self.status.value} a {new_status.value}.",
            )
        if new_status is DownloadStatus.FAILED and failure is None:
            raise DownloadDomainError("missing_failure", "El fallo requiere un error.")
        if new_status is DownloadStatus.COMPLETED and result is None:
            raise DownloadDomainError(
                "missing_result", "La finalización requiere resultado."
            )

        now = datetime.now(UTC)
        if new_status is DownloadStatus.DOWNLOADING:
            self.started_at = now
        if new_status in _TERMINAL_STATUSES:
            self.finished_at = now
        self.status = new_status
        self.failure = failure
        self.result = result

    def update_progress(self, progress: DownloadProgress) -> None:
        if self.status not in {DownloadStatus.DOWNLOADING, DownloadStatus.PROCESSING}:
            raise DownloadDomainError(
                "invalid_progress_state",
                "El progreso solo puede cambiar durante una descarga activa.",
            )
        self.progress = progress


@dataclass(slots=True)
class DownloadTask:
    id: UUID
    platform: Platform
    media_id: str
    title: str
    canonical_url: str
    selection: DownloadSelection
    created_at: datetime
    attempts: list[DownloadAttempt]

    @classmethod
    def create(
        cls,
        *,
        platform: Platform,
        media_id: str,
        title: str,
        canonical_url: str,
        selection: DownloadSelection,
    ) -> "DownloadTask":
        return cls(
            id=uuid4(),
            platform=platform,
            media_id=media_id,
            title=title,
            canonical_url=canonical_url,
            selection=selection,
            created_at=datetime.now(UTC),
            attempts=[DownloadAttempt(number=1)],
        )

    @property
    def current_attempt(self) -> DownloadAttempt:
        return self.attempts[-1]

    @property
    def status(self) -> DownloadStatus:
        return self.current_attempt.status

    def start_new_attempt(self) -> DownloadAttempt:
        if self.status not in {DownloadStatus.FAILED, DownloadStatus.INTERRUPTED}:
            raise DownloadDomainError(
                "retry_not_allowed",
                "Solo se pueden reintentar descargas fallidas o interrumpidas.",
            )
        attempt = DownloadAttempt(number=len(self.attempts) + 1)
        self.attempts.append(attempt)
        return attempt
