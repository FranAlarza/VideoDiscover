"""FastAPI application factory."""

import os
import shutil
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.diagnostics import router as diagnostics_router
from app.api.downloads import router as downloads_router
from app.api.events import router as events_router
from app.api.health import router as health_router
from app.api.media import router as media_router
from app.config import Settings
from app.database.migrations import upgrade_database
from app.database.repository import SqliteDownloadRepository, create_sqlite_engine
from app.downloader.executor import SimulatedDownloadExecutor
from app.downloader.paths import DownloadPathPolicy
from app.downloader.repository import InMemoryDownloadRepository
from app.downloader.service import DownloadTaskService
from app.downloader.worker import DownloadWorker
from app.downloader.yt_dlp_executor import YtDlpDownloadExecutor
from app.events.broker import DownloadEventBroker
from app.media.inspection import MediaInspectionService
from app.media.validation import MediaUrlValidationService
from app.system.diagnostics import DependencyDiagnosticsService


def create_app(
    settings: Settings | None = None,
    diagnostics_service: DependencyDiagnosticsService | None = None,
    media_url_validator: MediaUrlValidationService | None = None,
    media_inspection_service: MediaInspectionService | None = None,
    download_task_service: DownloadTaskService | None = None,
    download_worker: DownloadWorker | None = None,
) -> FastAPI:
    """Create an isolated API application instance."""
    runtime_settings = settings or Settings.from_environment()
    runtime_diagnostics = diagnostics_service or DependencyDiagnosticsService()
    runtime_media_url_validator = media_url_validator or MediaUrlValidationService()
    runtime_media_inspection = media_inspection_service or MediaInspectionService(
        runtime_media_url_validator
    )
    runtime_worker = download_worker
    runtime_event_broker = DownloadEventBroker()
    if download_task_service is None:
        if runtime_settings.environment == "test":
            repository = InMemoryDownloadRepository()
        else:
            upgrade_database(runtime_settings.database_path)
            repository = SqliteDownloadRepository(
                create_sqlite_engine(runtime_settings.database_path)
            )
        if runtime_worker is None:
            executor = SimulatedDownloadExecutor()
            if runtime_settings.download_executor == "real":
                node_binary = os.getenv("VD_NODE_BINARY") or shutil.which("node")
                if not node_binary:
                    raise RuntimeError("Node.js is required by the real executor")
                executor = YtDlpDownloadExecutor(
                    DownloadPathPolicy(
                        output_root=runtime_settings.download_output_root,
                        temporary_root=runtime_settings.download_temporary_root,
                    ),
                    node_binary=node_binary,
                )
            runtime_worker = DownloadWorker(repository, executor, runtime_event_broker)
        runtime_download_tasks = DownloadTaskService(
            repository,
            runtime_media_url_validator,
            runtime_media_inspection,
            runtime_worker,
            runtime_event_broker,
        )
    else:
        runtime_download_tasks = download_task_service
    docs_url = "/docs" if runtime_settings.docs_enabled else None
    openapi_url = "/openapi.json" if runtime_settings.docs_enabled else None

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.system_diagnostics = runtime_diagnostics.inspect()
        application.state.media_url_validator = runtime_media_url_validator
        application.state.media_inspection_service = runtime_media_inspection
        application.state.download_task_service = runtime_download_tasks
        application.state.download_worker = runtime_worker
        application.state.download_event_broker = runtime_event_broker
        if runtime_worker is not None:
            await runtime_worker.start()
        try:
            yield
        finally:
            if runtime_worker is not None:
                await runtime_worker.shutdown()
            await runtime_media_inspection.shutdown()

    application = FastAPI(
        title=runtime_settings.app_name,
        docs_url=docs_url,
        redoc_url=None,
        openapi_url=openapi_url,
        lifespan=lifespan,
    )
    application.state.settings = runtime_settings
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[runtime_settings.frontend_origin],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    application.include_router(health_router)
    application.include_router(diagnostics_router)
    application.include_router(media_router)
    application.include_router(downloads_router)
    application.include_router(events_router)
    return application


app = create_app()
