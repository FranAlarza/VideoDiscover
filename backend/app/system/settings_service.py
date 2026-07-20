"""Application rules for local settings changes."""

from pathlib import Path

from app.database.settings_repository import LocalSettings, SettingsRepository
from app.downloader.domain import DownloadStatus
from app.downloader.repository import DownloadRepository
from app.downloader.worker import DownloadWorker
from app.system.download_directory import (
    DownloadDirectoryError,
    DownloadDirectoryValidator,
)


class LocalSettingsService:
    def __init__(
        self,
        settings_repository: SettingsRepository,
        download_repository: DownloadRepository,
        directory_validator: DownloadDirectoryValidator,
        *,
        default_output_root: Path,
        worker: DownloadWorker | None = None,
    ) -> None:
        self._settings_repository = settings_repository
        self._download_repository = download_repository
        self._directory_validator = directory_validator
        self._default_output_root = default_output_root
        self._worker = worker

    async def get(self) -> LocalSettings:
        return await self._settings_repository.get_or_create(self._default_output_root)

    async def update_download_output_root(self, candidate: str | Path) -> LocalSettings:
        tasks = await self._download_repository.list()
        if any(
            task.status
            in {
                DownloadStatus.QUEUED,
                DownloadStatus.DOWNLOADING,
                DownloadStatus.PROCESSING,
            }
            for task in tasks
        ):
            raise DownloadDirectoryError(
                "download_directory_change_blocked",
                (
                    "Espera a que terminen o cancela las descargas pendientes "
                    "antes de cambiar la carpeta."
                ),
                status_code=409,
            )
        validated = self._directory_validator.validate(candidate)
        if self._worker is not None:
            self._worker.update_output_root(validated)
        return await self._settings_repository.update_download_output_root(validated)
