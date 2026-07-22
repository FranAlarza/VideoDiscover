import asyncio
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.database.migrations import upgrade_database
from app.database.repository import create_sqlite_engine
from app.database.settings_repository import SqliteSettingsRepository
from app.downloader.domain import (
    DownloadSelection,
    DownloadStatus,
    DownloadTask,
    OutputType,
    VideoQuality,
)
from app.downloader.repository import InMemoryDownloadRepository
from app.models.media import Platform
from app.system.download_directory import (
    DownloadDirectoryError,
    DownloadDirectoryValidator,
)
from app.system.settings_service import LocalSettingsService


def _validator(tmp_path: Path) -> DownloadDirectoryValidator:
    return DownloadDirectoryValidator(temporary_root=tmp_path / "temporary")


def test_directory_validator_creates_and_tests_a_writable_directory(
    tmp_path: Path,
) -> None:
    selected = tmp_path / "nested" / "downloads"

    resolved = _validator(tmp_path).validate(selected)

    assert resolved == selected.resolve()
    assert resolved.is_dir()
    assert list(resolved.iterdir()) == []


@pytest.mark.parametrize("candidate", ["", "relative/path", "/"])
def test_directory_validator_rejects_invalid_or_broad_paths(
    tmp_path: Path, candidate: str
) -> None:
    with pytest.raises(DownloadDirectoryError) as raised:
        _validator(tmp_path).validate(candidate)

    assert raised.value.code in {
        "invalid_download_directory",
        "unsafe_download_directory",
    }


def test_directory_validator_rejects_a_file_and_the_temporary_tree(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "file.mp4"
    file_path.write_bytes(b"video")
    validator = _validator(tmp_path)

    with pytest.raises(DownloadDirectoryError) as file_error:
        validator.validate(file_path)
    with pytest.raises(DownloadDirectoryError) as temporary_error:
        validator.validate(tmp_path / "temporary" / "nested")

    assert file_error.value.code == "download_directory_not_writable"
    assert temporary_error.value.code == "unsafe_download_directory"


def test_settings_service_blocks_changes_while_queue_has_work(tmp_path: Path) -> None:
    async def scenario() -> None:
        repository = InMemoryDownloadRepository()
        await repository.create(_task())
        service = _service(tmp_path, repository)

        with pytest.raises(DownloadDirectoryError) as raised:
            await service.update_download_output_root(tmp_path / "selected")

        assert raised.value.code == "download_directory_change_blocked"

    asyncio.run(scenario())


def test_settings_service_persists_validated_path_after_terminal_work(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        repository = InMemoryDownloadRepository()
        task = await repository.create(_task())
        task.current_attempt.transition_to(DownloadStatus.CANCELLED)
        await repository.save(task)
        service = _service(tmp_path, repository)
        selected = tmp_path / "selected"

        settings = await service.update_download_output_root(selected)
        restarted = await service.get()

        assert settings.download_output_root == selected.resolve()
        assert restarted == settings

    asyncio.run(scenario())


def test_settings_service_updates_worker_before_persisting_path(tmp_path: Path) -> None:
    async def scenario() -> None:
        downloads = InMemoryDownloadRepository()
        database_path = tmp_path / "settings.sqlite3"
        upgrade_database(database_path)
        settings = SqliteSettingsRepository(create_sqlite_engine(database_path))
        worker = Mock()
        selected = tmp_path / "selected"
        service = LocalSettingsService(
            settings,
            downloads,
            _validator(tmp_path),
            default_output_root=tmp_path / "default",
            worker=worker,
        )

        persisted = await service.update_download_output_root(selected)

        worker.update_output_root.assert_called_once_with(selected.resolve())
        assert persisted.download_output_root == selected.resolve()

    asyncio.run(scenario())


def test_settings_service_recovers_the_local_default_for_startup(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        downloads = InMemoryDownloadRepository()
        database_path = tmp_path / "settings.sqlite3"
        upgrade_database(database_path)
        settings_repository = SqliteSettingsRepository(
            create_sqlite_engine(database_path)
        )
        worker = Mock()
        default_root = tmp_path / "local-downloads"
        service = LocalSettingsService(
            settings_repository,
            downloads,
            _validator(tmp_path),
            default_output_root=default_root,
            worker=worker,
        )
        await settings_repository.update_download_output_root(
            Path("/Volumes/Disconnected/Downloads")
        )

        recovered = await service.recover_default_output_root()
        persisted = await service.get()

        assert recovered.download_output_root == default_root.resolve()
        assert persisted == recovered
        worker.update_output_root.assert_called_once_with(default_root.resolve())

    asyncio.run(scenario())


def _service(
    tmp_path: Path, downloads: InMemoryDownloadRepository
) -> LocalSettingsService:
    database_path = tmp_path / "settings.sqlite3"
    upgrade_database(database_path)
    settings = SqliteSettingsRepository(create_sqlite_engine(database_path))
    return LocalSettingsService(
        settings,
        downloads,
        _validator(tmp_path),
        default_output_root=tmp_path / "default",
    )


def _task() -> DownloadTask:
    return DownloadTask.create(
        platform=Platform.YOUTUBE,
        media_id="example",
        title="Example",
        canonical_url="https://www.youtube.com/watch?v=example",
        selection=DownloadSelection(OutputType.VIDEO, VideoQuality.P720),
    )
