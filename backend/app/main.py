"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.diagnostics import router as diagnostics_router
from app.api.downloads import router as downloads_router
from app.api.health import router as health_router
from app.api.media import router as media_router
from app.config import Settings
from app.downloader.repository import InMemoryDownloadRepository
from app.downloader.service import DownloadTaskService
from app.media.inspection import MediaInspectionService
from app.media.validation import MediaUrlValidationService
from app.system.diagnostics import DependencyDiagnosticsService


def create_app(
    settings: Settings | None = None,
    diagnostics_service: DependencyDiagnosticsService | None = None,
    media_url_validator: MediaUrlValidationService | None = None,
    media_inspection_service: MediaInspectionService | None = None,
    download_task_service: DownloadTaskService | None = None,
) -> FastAPI:
    """Create an isolated API application instance."""
    runtime_settings = settings or Settings.from_environment()
    runtime_diagnostics = diagnostics_service or DependencyDiagnosticsService()
    runtime_media_url_validator = media_url_validator or MediaUrlValidationService()
    runtime_media_inspection = media_inspection_service or MediaInspectionService(
        runtime_media_url_validator
    )
    runtime_download_tasks = download_task_service or DownloadTaskService(
        InMemoryDownloadRepository(),
        runtime_media_url_validator,
        runtime_media_inspection,
    )
    docs_url = "/docs" if runtime_settings.docs_enabled else None
    openapi_url = "/openapi.json" if runtime_settings.docs_enabled else None

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.system_diagnostics = runtime_diagnostics.inspect()
        application.state.media_url_validator = runtime_media_url_validator
        application.state.media_inspection_service = runtime_media_inspection
        application.state.download_task_service = runtime_download_tasks
        try:
            yield
        finally:
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
    return application


app = create_app()
