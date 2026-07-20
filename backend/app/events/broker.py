"""Bounded in-memory event broker for download state changes."""

import asyncio
import time
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.downloader.domain import DownloadStatus, DownloadTask


@dataclass(frozen=True, slots=True)
class DownloadEvent:
    id: int
    name: str
    occurred_at: datetime
    data: dict[str, Any]


@dataclass(frozen=True, slots=True)
class EventSubscription:
    queue: asyncio.Queue[DownloadEvent]
    replay: tuple[DownloadEvent, ...]
    requires_snapshot: bool


class DownloadEventBroker:
    def __init__(
        self,
        *,
        subscriber_queue_size: int = 64,
        history_size: int = 256,
        progress_interval_seconds: float = 0.2,
    ) -> None:
        self._subscriber_queue_size = subscriber_queue_size
        self._history: deque[DownloadEvent] = deque(maxlen=history_size)
        self._subscribers: set[asyncio.Queue[DownloadEvent]] = set()
        self._sequence = 0
        self._lock = asyncio.Lock()
        self._last_progress: dict[UUID, float] = {}
        self._progress_interval_seconds = progress_interval_seconds

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    async def publish(
        self,
        task: DownloadTask,
        *,
        name: str = "download.updated",
        queue_position: int | None = None,
        force: bool = False,
    ) -> DownloadEvent | None:
        if force and task.status not in {
            DownloadStatus.DOWNLOADING,
            DownloadStatus.PROCESSING,
        }:
            self._last_progress.pop(task.id, None)
        if not force and not self._should_publish_progress(task):
            return None
        async with self._lock:
            self._sequence += 1
            event = DownloadEvent(
                id=self._sequence,
                name=name,
                occurred_at=datetime.now(UTC),
                data=_public_task_data(task, queue_position),
            )
            self._history.append(event)
            for queue in self._subscribers:
                if queue.full():
                    while not queue.empty():
                        queue.get_nowait()
                    queue.put_nowait(
                        DownloadEvent(
                            id=event.id,
                            name="downloads.resync",
                            occurred_at=event.occurred_at,
                            data={},
                        )
                    )
                else:
                    queue.put_nowait(event)
            return event

    def _should_publish_progress(self, task: DownloadTask) -> bool:
        if task.status not in {DownloadStatus.DOWNLOADING, DownloadStatus.PROCESSING}:
            self._last_progress.pop(task.id, None)
            return True
        now = time.monotonic()
        previous = self._last_progress.get(task.id)
        if previous is not None and now - previous < self._progress_interval_seconds:
            return False
        self._last_progress[task.id] = now
        return True

    async def subscribe(self, last_event_id: int | None = None) -> EventSubscription:
        async with self._lock:
            queue: asyncio.Queue[DownloadEvent] = asyncio.Queue(
                maxsize=self._subscriber_queue_size
            )
            self._subscribers.add(queue)
            if last_event_id is None:
                return EventSubscription(queue, (), True)
            oldest = self._history[0].id if self._history else self._sequence + 1
            if last_event_id < oldest - 1 or last_event_id > self._sequence:
                return EventSubscription(queue, (), True)
            replay = tuple(event for event in self._history if event.id > last_event_id)
            return EventSubscription(queue, replay, False)

    async def unsubscribe(self, subscription: EventSubscription) -> None:
        async with self._lock:
            self._subscribers.discard(subscription.queue)


def _public_task_data(task: DownloadTask, queue_position: int | None) -> dict[str, Any]:
    attempts = [_public_attempt_data(attempt) for attempt in task.attempts]
    return {
        "id": str(task.id),
        "platform": task.platform.value,
        "media_id": task.media_id,
        "title": task.title,
        "status": task.status.value,
        "queue_position": queue_position,
        "selection": {
            "output_type": task.selection.output_type.value,
            "video_quality": (
                task.selection.video_quality.value
                if task.selection.video_quality is not None
                else None
            ),
            "audio_bitrate": (
                task.selection.audio_bitrate.value
                if task.selection.audio_bitrate is not None
                else None
            ),
        },
        "created_at": task.created_at.isoformat().replace("+00:00", "Z"),
        "current_attempt": attempts[-1],
        "attempts": attempts,
    }


def _public_attempt_data(attempt) -> dict[str, Any]:
    return {
        "number": attempt.number,
        "status": attempt.status.value,
        "created_at": _date(attempt.created_at),
        "started_at": _date(attempt.started_at),
        "finished_at": _date(attempt.finished_at),
        "progress": {
            "percentage": attempt.progress.percentage,
            "downloaded_bytes": attempt.progress.downloaded_bytes,
            "total_bytes": attempt.progress.total_bytes,
            "speed_bytes_per_second": attempt.progress.speed_bytes_per_second,
            "eta_seconds": attempt.progress.eta_seconds,
        },
        "failure": (
            {"code": attempt.failure.code, "message": attempt.failure.message}
            if attempt.failure
            else None
        ),
        "result": (
            {
                "filename": attempt.result.filename,
                "extension": attempt.result.extension,
                "size_bytes": attempt.result.size_bytes,
                "effective_quality": attempt.result.effective_quality,
            }
            if attempt.result
            else None
        ),
    }


def _date(value: datetime | None) -> str | None:
    return value.isoformat().replace("+00:00", "Z") if value else None
