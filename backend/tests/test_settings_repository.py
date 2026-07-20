import asyncio
from pathlib import Path

from sqlalchemy import inspect, text

from app.database.migrations import upgrade_database
from app.database.repository import create_sqlite_engine
from app.database.settings_repository import SqliteSettingsRepository


def test_settings_repository_creates_the_configured_default(tmp_path: Path) -> None:
    database_path = tmp_path / "settings.sqlite3"
    upgrade_database(database_path)
    repository = SqliteSettingsRepository(create_sqlite_engine(database_path))
    default_root = tmp_path / "downloads"

    settings = asyncio.run(repository.get_or_create(default_root))

    assert settings.download_output_root == default_root.resolve()


def test_settings_repository_persists_output_root_across_instances(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "settings.sqlite3"
    upgrade_database(database_path)
    first = SqliteSettingsRepository(create_sqlite_engine(database_path))
    selected_root = tmp_path / "selected"
    asyncio.run(first.update_download_output_root(selected_root))

    restarted = SqliteSettingsRepository(create_sqlite_engine(database_path))
    settings = asyncio.run(restarted.get_or_create(tmp_path / "ignored-default"))

    assert settings.download_output_root == selected_root.resolve()


def test_settings_migration_upgrades_an_existing_download_database(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "existing.sqlite3"
    upgrade_database(database_path)
    engine = create_sqlite_engine(database_path)
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE settings")
        connection.exec_driver_sql(
            "ALTER TABLE download_attempts DROP COLUMN result_output_directory"
        )
        connection.execute(
            text("UPDATE alembic_version SET version_num = '20260720_01'")
        )
    engine.dispose()

    upgrade_database(database_path)

    tables = set(inspect(create_sqlite_engine(database_path)).get_table_names())
    assert "settings" in tables
