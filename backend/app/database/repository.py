"""SQLite implementation of the download repository."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import create_engine, event, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, selectinload

from app.database.models import Base, DownloadAttemptRecord, DownloadRecord
from app.downloader.domain import (
    AudioBitrate,
    DownloadAttempt,
    DownloadFailure,
    DownloadProgress,
    DownloadResult,
    DownloadSelection,
    DownloadStatus,
    DownloadTask,
    OutputType,
    VideoQuality,
)
from app.models.media import Platform


def create_sqlite_engine(database_path: Path) -> Engine:
    database_path = database_path.expanduser().resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    engine = create_engine(f"sqlite:///{database_path}")

    @event.listens_for(engine, "connect")
    def configure_sqlite(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    return engine


class SqliteDownloadRepository:
    def __init__(self, engine: Engine, *, create_schema: bool = False) -> None:
        self._engine = engine
        self._lock = asyncio.Lock()
        self._live_progress: dict[UUID, DownloadProgress] = {}
        if create_schema:
            Base.metadata.create_all(engine)

    async def create(self, task: DownloadTask) -> DownloadTask:
        async with self._lock:
            await asyncio.to_thread(self._create_sync, task)
        return deepcopy(task)

    def _create_sync(self, task: DownloadTask) -> None:
        with Session(self._engine) as session, session.begin():
            if session.get(DownloadRecord, str(task.id)) is not None:
                raise ValueError("Download task already exists")
            session.add(_to_record(task))

    async def get(self, task_id: UUID) -> DownloadTask | None:
        async with self._lock:
            task = await asyncio.to_thread(self._get_sync, task_id)
            return self._with_live_progress(task)

    def _get_sync(self, task_id: UUID) -> DownloadTask | None:
        with Session(self._engine) as session:
            record = session.scalar(
                select(DownloadRecord)
                .where(DownloadRecord.id == str(task_id))
                .options(selectinload(DownloadRecord.attempts))
            )
            return _to_domain(record) if record is not None else None

    async def list(self) -> list[DownloadTask]:
        async with self._lock:
            tasks = await asyncio.to_thread(self._list_sync)
            return [self._with_live_progress(task) for task in tasks]

    def _list_sync(self) -> list[DownloadTask]:
        with Session(self._engine) as session:
            records = session.scalars(
                select(DownloadRecord)
                .options(selectinload(DownloadRecord.attempts))
                .order_by(DownloadRecord.created_at, DownloadRecord.id)
            ).all()
            return [_to_domain(record) for record in records]

    async def save(self, task: DownloadTask) -> DownloadTask:
        async with self._lock:
            await asyncio.to_thread(self._save_sync, task)
            self._live_progress.pop(task.id, None)
        return deepcopy(task)

    def _save_sync(self, task: DownloadTask) -> None:
        with Session(self._engine) as session, session.begin():
            existing = session.get(DownloadRecord, str(task.id))
            if existing is None:
                raise KeyError(task.id)
            session.delete(existing)
            session.flush()
            session.add(_to_record(task))

    async def update_progress(self, task: DownloadTask) -> None:
        async with self._lock:
            self._live_progress[task.id] = deepcopy(task.current_attempt.progress)

    async def delete(self, task_id: UUID) -> None:
        async with self._lock:
            deleted = await asyncio.to_thread(self._delete_sync, task_id)
            if not deleted:
                raise KeyError(task_id)
            self._live_progress.pop(task_id, None)

    def _delete_sync(self, task_id: UUID) -> bool:
        with Session(self._engine) as session, session.begin():
            existing = session.get(DownloadRecord, str(task_id))
            if existing is None:
                return False
            session.delete(existing)
            return True

    async def claim_next_queued(self) -> DownloadTask | None:
        async with self._lock:
            return await asyncio.to_thread(self._claim_next_sync)

    def _claim_next_sync(self) -> DownloadTask | None:
        with Session(self._engine) as session:
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            record = session.scalar(
                select(DownloadRecord)
                .join(DownloadAttemptRecord)
                .where(DownloadAttemptRecord.status == DownloadStatus.QUEUED.value)
                .options(selectinload(DownloadRecord.attempts))
                .order_by(DownloadRecord.created_at, DownloadRecord.id)
                .limit(1)
            )
            if record is None:
                session.commit()
                return None
            task = _to_domain(record)
            task.current_attempt.transition_to(DownloadStatus.DOWNLOADING)
            _update_attempt(record.attempts[-1], task.current_attempt)
            session.commit()
            return task

    async def interrupt_active(self) -> int:
        async with self._lock:
            count = await asyncio.to_thread(self._interrupt_active_sync)
            self._live_progress.clear()
            return count

    def _interrupt_active_sync(self) -> int:
        with Session(self._engine) as session, session.begin():
            records = session.scalars(
                select(DownloadAttemptRecord).where(
                    DownloadAttemptRecord.status.in_(
                        [
                            DownloadStatus.DOWNLOADING.value,
                            DownloadStatus.PROCESSING.value,
                        ]
                    )
                )
            ).all()
            for record in records:
                record.status = DownloadStatus.INTERRUPTED.value
                record.finished_at = datetime.now(UTC)
            return len(records)

    def _with_live_progress(self, task: DownloadTask | None) -> DownloadTask | None:
        if task is None:
            return None
        progress = self._live_progress.get(task.id)
        if progress is not None:
            task.current_attempt.progress = deepcopy(progress)
        return task


def _to_record(task: DownloadTask) -> DownloadRecord:
    return DownloadRecord(
        id=str(task.id),
        platform=task.platform.value,
        media_id=task.media_id,
        title=task.title,
        canonical_url=task.canonical_url,
        output_type=task.selection.output_type.value,
        video_quality=(
            task.selection.video_quality.value
            if task.selection.video_quality is not None
            else None
        ),
        audio_bitrate=(
            task.selection.audio_bitrate.value
            if task.selection.audio_bitrate is not None
            else None
        ),
        created_at=task.created_at,
        attempts=[_attempt_to_record(attempt) for attempt in task.attempts],
    )


def _attempt_to_record(attempt: DownloadAttempt) -> DownloadAttemptRecord:
    record = DownloadAttemptRecord(download_id="", number=attempt.number)
    _update_attempt(record, attempt)
    return record


def _update_attempt(record: DownloadAttemptRecord, attempt: DownloadAttempt) -> None:
    record.status = attempt.status.value
    record.created_at = attempt.created_at
    record.started_at = attempt.started_at
    record.finished_at = attempt.finished_at
    record.percentage = attempt.progress.percentage
    record.downloaded_bytes = attempt.progress.downloaded_bytes
    record.total_bytes = attempt.progress.total_bytes
    record.speed_bytes_per_second = attempt.progress.speed_bytes_per_second
    record.eta_seconds = attempt.progress.eta_seconds
    record.failure_code = attempt.failure.code if attempt.failure else None
    record.failure_message = attempt.failure.message if attempt.failure else None
    record.result_filename = attempt.result.filename if attempt.result else None
    record.result_extension = attempt.result.extension if attempt.result else None
    record.result_size_bytes = attempt.result.size_bytes if attempt.result else None
    record.result_effective_quality = (
        attempt.result.effective_quality if attempt.result else None
    )


def _to_domain(record: DownloadRecord) -> DownloadTask:
    return DownloadTask(
        id=UUID(record.id),
        platform=Platform(record.platform),
        media_id=record.media_id,
        title=record.title,
        canonical_url=record.canonical_url,
        selection=DownloadSelection(
            output_type=OutputType(record.output_type),
            video_quality=(
                VideoQuality(record.video_quality)
                if record.video_quality is not None
                else None
            ),
            audio_bitrate=(
                AudioBitrate(record.audio_bitrate)
                if record.audio_bitrate is not None
                else None
            ),
        ),
        created_at=_utc(record.created_at),
        attempts=[_attempt_to_domain(attempt) for attempt in record.attempts],
    )


def _attempt_to_domain(record: DownloadAttemptRecord) -> DownloadAttempt:
    return DownloadAttempt(
        number=record.number,
        status=DownloadStatus(record.status),
        created_at=_utc(record.created_at),
        started_at=_utc(record.started_at),
        finished_at=_utc(record.finished_at),
        progress=DownloadProgress(
            percentage=record.percentage,
            downloaded_bytes=record.downloaded_bytes,
            total_bytes=record.total_bytes,
            speed_bytes_per_second=record.speed_bytes_per_second,
            eta_seconds=record.eta_seconds,
        ),
        failure=(
            DownloadFailure(record.failure_code, record.failure_message)
            if record.failure_code and record.failure_message
            else None
        ),
        result=(
            DownloadResult(
                filename=record.result_filename,
                extension=record.result_extension,
                size_bytes=record.result_size_bytes,
                effective_quality=record.result_effective_quality,
            )
            if record.result_filename
            and record.result_extension
            and record.result_size_bytes is not None
            else None
        ),
    )


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
