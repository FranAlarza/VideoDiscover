"""Programmatic Alembic migration entry point."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def upgrade_database(database_path: Path) -> None:
    backend_root = Path(__file__).resolve().parents[2]
    config = Config(str(backend_root / "alembic.ini"))
    resolved = database_path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    config.set_main_option("sqlalchemy.url", f"sqlite:///{resolved}")
    _stamp_complete_unversioned_schema(config, resolved)
    command.upgrade(config, "head")


def _stamp_complete_unversioned_schema(config: Config, database_path: Path) -> None:
    """Recover SQLite DDL committed before Alembic could persist its version."""
    if not database_path.exists():
        return
    engine = create_engine(f"sqlite:///{database_path}")
    tables = set(inspect(engine).get_table_names())
    expected = {"downloads", "download_attempts", "alembic_version"}
    if not expected <= tables:
        engine.dispose()
        return
    with engine.connect() as connection:
        version = connection.scalar(text("SELECT version_num FROM alembic_version"))
    engine.dispose()
    if version is None:
        command.stamp(config, "head")
