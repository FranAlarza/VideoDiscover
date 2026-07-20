"""Single-consumer FIFO download worker."""

import asyncio
from contextlib import suppress
from uuid import UUID

from app.downloader.domain import DownloadFailure, DownloadProgress, DownloadStatus
from app.downloader.executor import (
    DownloadCancelled,
    DownloadExecutionError,
    DownloadExecutor,
)
from app.downloader.repository import DownloadRepository
from app.events.broker import DownloadEventBroker


class DownloadWorker:
    def __init__(
        self,
        repository: DownloadRepository,
        executor: DownloadExecutor,
        event_broker: DownloadEventBroker | None = None,
    ) -> None:
        self._repository = repository
        self._executor = executor
        self._event_broker = event_broker
        self._wake_event = asyncio.Event()
        self._stop_event = asyncio.Event()
        self._runner: asyncio.Task[None] | None = None
        self._active_id: UUID | None = None
        self._active_cancel: asyncio.Event | None = None

    async def start(self) -> None:
        if self._runner is not None:
            return
        await self._repository.interrupt_active()
        self._stop_event.clear()
        self._runner = asyncio.create_task(self._run(), name="download-worker")
        self.notify()

    def notify(self) -> None:
        self._wake_event.set()

    def request_cancel(self, task_id: UUID) -> bool:
        if self._active_id != task_id or self._active_cancel is None:
            return False
        self._active_cancel.set()
        return True

    async def shutdown(self) -> None:
        if self._runner is None:
            return
        self._stop_event.set()
        if self._active_cancel is not None:
            self._active_cancel.set()
        self.notify()
        with suppress(asyncio.CancelledError):
            await self._runner
        self._runner = None

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            self._wake_event.clear()
            task = await self._repository.claim_next_queued()
            if task is None:
                await self._wake_event.wait()
                continue
            self._active_id = task.id
            self._active_cancel = asyncio.Event()
            try:
                await self._publish(task, force=True)
                await self._execute(task)
            finally:
                self._active_id = None
                self._active_cancel = None

    async def _execute(self, task) -> None:
        cancel_event = self._active_cancel
        if cancel_event is None:
            raise RuntimeError("active cancellation token is missing")

        async def update_progress(progress: DownloadProgress) -> None:
            task.current_attempt.update_progress(progress)
            await self._repository.update_progress(task)
            await self._publish(task)

        async def begin_processing() -> None:
            task.current_attempt.transition_to(DownloadStatus.PROCESSING)
            await self._repository.save(task)
            await self._publish(task, force=True)

        try:
            result = await self._executor.execute(
                task,
                on_progress=update_progress,
                on_processing=begin_processing,
                cancel_event=cancel_event,
            )
        except DownloadCancelled:
            task.current_attempt.transition_to(DownloadStatus.CANCELLED)
        except DownloadExecutionError as error:
            task.current_attempt.transition_to(
                DownloadStatus.FAILED,
                failure=DownloadFailure(error.code, error.message),
            )
        except Exception:
            task.current_attempt.transition_to(
                DownloadStatus.FAILED,
                failure=DownloadFailure(
                    "unknown_error", "No se pudo completar la descarga."
                ),
            )
        else:
            task.current_attempt.transition_to(DownloadStatus.COMPLETED, result=result)
        await self._repository.save(task)
        await self._publish(task, force=True)

    async def _publish(self, task, *, force: bool = False) -> None:
        if self._event_broker is None:
            return
        await self._event_broker.publish(task, force=force)
