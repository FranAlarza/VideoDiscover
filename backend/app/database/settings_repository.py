"""Persistent local application settings."""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.database.models import SettingRecord

_DOWNLOAD_OUTPUT_ROOT = "download_output_root"


@dataclass(frozen=True, slots=True)
class LocalSettings:
    download_output_root: Path


class SettingsRepository(Protocol):
    async def get_or_create(self, default_output_root: Path) -> LocalSettings: ...

    async def update_download_output_root(self, output_root: Path) -> LocalSettings: ...


class SqliteSettingsRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._lock = asyncio.Lock()

    async def get_or_create(self, default_output_root: Path) -> LocalSettings:
        resolved_default = default_output_root.expanduser().resolve()
        async with self._lock:
            value = await asyncio.to_thread(self._get_or_create_sync, resolved_default)
        return LocalSettings(download_output_root=Path(value))

    async def update_download_output_root(self, output_root: Path) -> LocalSettings:
        resolved = output_root.expanduser().resolve()
        async with self._lock:
            await asyncio.to_thread(
                self._set_sync, _DOWNLOAD_OUTPUT_ROOT, str(resolved)
            )
        return LocalSettings(download_output_root=resolved)

    def _get_or_create_sync(self, default_output_root: Path) -> str:
        with Session(self._engine) as session, session.begin():
            record = session.get(SettingRecord, _DOWNLOAD_OUTPUT_ROOT)
            if record is None:
                record = SettingRecord(
                    key=_DOWNLOAD_OUTPUT_ROOT,
                    value=str(default_output_root),
                    updated_at=datetime.now(UTC),
                )
                session.add(record)
            return record.value

    def _set_sync(self, key: str, value: str) -> None:
        with Session(self._engine) as session, session.begin():
            record = session.get(SettingRecord, key)
            if record is None:
                session.add(
                    SettingRecord(
                        key=key,
                        value=value,
                        updated_at=datetime.now(UTC),
                    )
                )
                return
            record.value = value
            record.updated_at = datetime.now(UTC)
