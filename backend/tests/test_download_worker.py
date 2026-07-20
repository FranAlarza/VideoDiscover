import asyncio
from collections.abc import Awaitable, Callable

from app.downloader.domain import (
    DownloadProgress,
    DownloadResult,
    DownloadSelection,
    DownloadStatus,
    DownloadTask,
    OutputType,
    VideoQuality,
)
from app.downloader.executor import DownloadExecutionError
from app.downloader.repository import InMemoryDownloadRepository
from app.downloader.worker import DownloadWorker
from app.models.media import Platform


def _task(title: str) -> DownloadTask:
    return DownloadTask.create(
        platform=Platform.YOUTUBE,
        media_id=title,
        title=title,
        canonical_url=f"https://www.youtube.com/watch?v={title}",
        selection=DownloadSelection(OutputType.VIDEO, VideoQuality.P720),
    )


async def _wait_for_status(
    repository: InMemoryDownloadRepository,
    task: DownloadTask,
    status: DownloadStatus,
) -> DownloadTask:
    async with asyncio.timeout(1):
        while True:
            stored = await repository.get(task.id)
            assert stored is not None
            if stored.status is status:
                return stored
            await asyncio.sleep(0.005)


class RecordingExecutor:
    def __init__(self, *, fail_title: str | None = None) -> None:
        self.started: list[str] = []
        self.fail_title = fail_title

    async def execute(
        self,
        task: DownloadTask,
        *,
        on_progress: Callable[[DownloadProgress], Awaitable[None]],
        on_processing: Callable[[], Awaitable[None]],
        cancel_event: asyncio.Event,
    ) -> DownloadResult:
        self.started.append(task.title)
        await on_progress(DownloadProgress(percentage=50))
        if self.fail_title == task.title:
            raise DownloadExecutionError("network_error", "Conexión interrumpida.")
        await on_processing()
        return DownloadResult(f"{task.title}.mp4", "mp4", 100, 720)


def test_worker_processes_tasks_in_fifo_order_and_survives_failure() -> None:
    async def scenario() -> None:
        repository = InMemoryDownloadRepository()
        first, second, third = _task("first"), _task("second"), _task("third")
        for task in (first, second, third):
            await repository.create(task)
        executor = RecordingExecutor(fail_title="second")
        worker = DownloadWorker(repository, executor)

        await worker.start()
        completed = await _wait_for_status(repository, third, DownloadStatus.COMPLETED)
        await worker.shutdown()

        assert executor.started == ["first", "second", "third"]
        assert (await repository.get(first.id)).status is DownloadStatus.COMPLETED
        failed = await repository.get(second.id)
        assert failed is not None
        assert failed.status is DownloadStatus.FAILED
        assert failed.current_attempt.failure.code == "network_error"
        assert completed.current_attempt.progress.percentage == 50
        assert completed.current_attempt.result.filename == "third.mp4"

    asyncio.run(scenario())


def test_worker_cancels_active_task_and_continues_queue() -> None:
    async def scenario() -> None:
        repository = InMemoryDownloadRepository()
        first, second = _task("first"), _task("second")
        await repository.create(first)
        await repository.create(second)
        from app.downloader.executor import SimulatedDownloadExecutor

        worker = DownloadWorker(
            repository, SimulatedDownloadExecutor(step_delay_seconds=0.02)
        )
        await worker.start()
        await _wait_for_status(repository, first, DownloadStatus.DOWNLOADING)

        assert worker.request_cancel(first.id)
        await _wait_for_status(repository, first, DownloadStatus.CANCELLED)
        await _wait_for_status(repository, second, DownloadStatus.COMPLETED)
        await worker.shutdown()

    asyncio.run(scenario())


def test_worker_interrupts_previously_active_tasks_on_start() -> None:
    async def scenario() -> None:
        repository = InMemoryDownloadRepository()
        task = _task("orphan")
        task.current_attempt.transition_to(DownloadStatus.DOWNLOADING)
        await repository.create(task)
        worker = DownloadWorker(repository, RecordingExecutor())

        await worker.start()
        stored = await repository.get(task.id)
        await worker.shutdown()

        assert stored is not None
        assert stored.status is DownloadStatus.INTERRUPTED

    asyncio.run(scenario())
