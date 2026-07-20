"""Download task repository contracts and in-memory implementation."""

import asyncio
from copy import deepcopy
from typing import Protocol
from uuid import UUID

from app.downloader.domain import DownloadTask


class DownloadRepository(Protocol):
    async def create(self, task: DownloadTask) -> DownloadTask: ...

    async def get(self, task_id: UUID) -> DownloadTask | None: ...

    async def list(self) -> list[DownloadTask]: ...

    async def save(self, task: DownloadTask) -> DownloadTask: ...


class InMemoryDownloadRepository:
    """Concurrency-safe repository used until SQLite is introduced."""

    def __init__(self) -> None:
        self._tasks: dict[UUID, DownloadTask] = {}
        self._lock = asyncio.Lock()

    async def create(self, task: DownloadTask) -> DownloadTask:
        async with self._lock:
            if task.id in self._tasks:
                raise ValueError("Download task already exists")
            self._tasks[task.id] = deepcopy(task)
            return deepcopy(task)

    async def get(self, task_id: UUID) -> DownloadTask | None:
        async with self._lock:
            task = self._tasks.get(task_id)
            return deepcopy(task) if task is not None else None

    async def list(self) -> list[DownloadTask]:
        async with self._lock:
            return [
                deepcopy(task)
                for task in sorted(
                    self._tasks.values(), key=lambda item: item.created_at
                )
            ]

    async def save(self, task: DownloadTask) -> DownloadTask:
        async with self._lock:
            if task.id not in self._tasks:
                raise KeyError(task.id)
            self._tasks[task.id] = deepcopy(task)
            return deepcopy(task)
