"""Download executor contract and a deterministic development implementation."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from app.downloader.domain import DownloadProgress, DownloadResult, DownloadTask

ProgressCallback = Callable[[DownloadProgress], Awaitable[None]]
ProcessingCallback = Callable[[], Awaitable[None]]


class DownloadCancelled(Exception):
    """Raised by an executor after it has stopped and cleaned its own work."""


class DownloadExecutionError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class DownloadExecutor(Protocol):
    async def execute(
        self,
        task: DownloadTask,
        *,
        on_progress: ProgressCallback,
        on_processing: ProcessingCallback,
        cancel_event: asyncio.Event,
    ) -> DownloadResult: ...


@dataclass(frozen=True, slots=True)
class SimulatedDownloadExecutor:
    """Exercise orchestration without network access or filesystem writes."""

    step_delay_seconds: float = 0.02
    progress_steps: tuple[int, ...] = (10, 40, 75, 100)
    include_processing: bool = True

    async def execute(
        self,
        task: DownloadTask,
        *,
        on_progress: ProgressCallback,
        on_processing: ProcessingCallback,
        cancel_event: asyncio.Event,
    ) -> DownloadResult:
        total_bytes = 1_000_000
        for percentage in self.progress_steps:
            await asyncio.sleep(self.step_delay_seconds)
            if cancel_event.is_set():
                raise DownloadCancelled
            await on_progress(
                DownloadProgress(
                    percentage=float(percentage),
                    downloaded_bytes=total_bytes * percentage // 100,
                    total_bytes=total_bytes,
                )
            )
        if self.include_processing:
            await on_processing()
            await asyncio.sleep(self.step_delay_seconds)
            if cancel_event.is_set():
                raise DownloadCancelled
        extension = "mp4" if task.selection.output_type.value == "video" else "mp3"
        return DownloadResult(
            filename=f"simulated-{task.id}.{extension}",
            extension=extension,
            size_bytes=total_bytes,
            effective_quality=(
                task.selection.video_quality.value
                if task.selection.video_quality is not None
                else None
            ),
        )
