import asyncio
from pathlib import Path

from sqlalchemy import inspect

from app.database.migrations import upgrade_database
from app.database.repository import SqliteDownloadRepository, create_sqlite_engine
from app.downloader.domain import (
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


def _task(title: str) -> DownloadTask:
    return DownloadTask.create(
        platform=Platform.YOUTUBE,
        media_id=title,
        title=title,
        canonical_url=f"https://www.youtube.com/watch?v={title}",
        selection=DownloadSelection(OutputType.VIDEO, VideoQuality.P720),
    )


def _repository(tmp_path: Path) -> SqliteDownloadRepository:
    return SqliteDownloadRepository(
        create_sqlite_engine(tmp_path / "downloads.sqlite3"), create_schema=True
    )


def test_migration_creates_current_schema_on_empty_database(tmp_path: Path) -> None:
    database_path = tmp_path / "migrated.sqlite3"

    upgrade_database(database_path)

    tables = set(inspect(create_sqlite_engine(database_path)).get_table_names())
    assert {"alembic_version", "downloads", "download_attempts"} <= tables


def test_sqlite_repository_round_trips_completed_task(tmp_path: Path) -> None:
    async def scenario() -> None:
        repository = _repository(tmp_path)
        task = _task("completed")
        await repository.create(task)
        claimed = await repository.claim_next_queued()
        assert claimed is not None
        claimed.current_attempt.update_progress(
            DownloadProgress(percentage=100, downloaded_bytes=10, total_bytes=10)
        )
        claimed.current_attempt.transition_to(
            DownloadStatus.COMPLETED,
            result=DownloadResult("Example.mp4", "mp4", 10, 720),
        )
        await repository.save(claimed)

        reloaded = await repository.get(task.id)

        assert reloaded is not None
        assert reloaded.status is DownloadStatus.COMPLETED
        assert reloaded.current_attempt.result.filename == "Example.mp4"
        assert reloaded.current_attempt.progress.percentage == 100
        assert reloaded.created_at.tzinfo is not None

    asyncio.run(scenario())


def test_sqlite_repository_claims_fifo_once(tmp_path: Path) -> None:
    async def scenario() -> None:
        repository = _repository(tmp_path)
        first, second = _task("first"), _task("second")
        await repository.create(first)
        await repository.create(second)

        claimed = await asyncio.gather(
            repository.claim_next_queued(), repository.claim_next_queued()
        )

        assert [task.title for task in claimed if task is not None] == [
            "first",
            "second",
        ]
        assert await repository.claim_next_queued() is None

    asyncio.run(scenario())


def test_live_progress_is_visible_but_not_written_per_update(tmp_path: Path) -> None:
    async def scenario() -> None:
        database_path = tmp_path / "downloads.sqlite3"
        engine = create_sqlite_engine(database_path)
        repository = SqliteDownloadRepository(engine, create_schema=True)
        task = _task("progress")
        await repository.create(task)
        active = await repository.claim_next_queued()
        assert active is not None
        active.current_attempt.update_progress(DownloadProgress(percentage=42))
        await repository.update_progress(active)

        live = await repository.get(task.id)
        restarted = await SqliteDownloadRepository(engine).get(task.id)

        assert live.current_attempt.progress.percentage == 42
        assert restarted.current_attempt.progress.percentage is None

    asyncio.run(scenario())


def test_restart_interrupts_active_and_keeps_queued_order(tmp_path: Path) -> None:
    async def scenario() -> None:
        database_path = tmp_path / "downloads.sqlite3"
        first_repository = SqliteDownloadRepository(
            create_sqlite_engine(database_path), create_schema=True
        )
        active, queued = _task("active"), _task("queued")
        await first_repository.create(active)
        await first_repository.create(queued)
        await first_repository.claim_next_queued()

        restarted = SqliteDownloadRepository(create_sqlite_engine(database_path))
        assert await restarted.interrupt_active() == 1
        tasks = await restarted.list()

        assert [task.status for task in tasks] == [
            DownloadStatus.INTERRUPTED,
            DownloadStatus.QUEUED,
        ]
        claimed = await restarted.claim_next_queued()
        assert claimed is not None
        assert claimed.title == "queued"

    asyncio.run(scenario())


def test_two_repository_instances_cannot_claim_same_task(tmp_path: Path) -> None:
    async def scenario() -> None:
        database_path = tmp_path / "downloads.sqlite3"
        first = SqliteDownloadRepository(
            create_sqlite_engine(database_path), create_schema=True
        )
        second = SqliteDownloadRepository(create_sqlite_engine(database_path))
        task = _task("single")
        await first.create(task)

        claims = await asyncio.gather(
            first.claim_next_queued(), second.claim_next_queued()
        )

        assert sum(claim is not None for claim in claims) == 1
        assert next(claim for claim in claims if claim is not None).id == task.id

    asyncio.run(scenario())


def test_sqlite_repository_preserves_all_retry_attempts(tmp_path: Path) -> None:
    async def scenario() -> None:
        repository = _repository(tmp_path)
        task = _task("retry")
        task.current_attempt.transition_to(DownloadStatus.DOWNLOADING)
        task.current_attempt.transition_to(
            DownloadStatus.FAILED,
            failure=DownloadFailure("network_error", "Connection failed"),
        )
        task.start_new_attempt()
        await repository.create(task)

        restarted = SqliteDownloadRepository(
            create_sqlite_engine(tmp_path / "downloads.sqlite3")
        )
        stored = await restarted.get(task.id)

        assert stored is not None
        assert [attempt.number for attempt in stored.attempts] == [1, 2]
        assert [attempt.status for attempt in stored.attempts] == [
            DownloadStatus.FAILED,
            DownloadStatus.QUEUED,
        ]
        assert stored.attempts[0].failure.code == "network_error"

    asyncio.run(scenario())
