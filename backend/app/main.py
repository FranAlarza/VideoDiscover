"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.diagnostics import router as diagnostics_router
from app.api.health import router as health_router
from app.api.media import router as media_router
from app.config import Settings
from app.media.validation import MediaUrlValidationService
from app.system.diagnostics import DependencyDiagnosticsService


def create_app(
    settings: Settings | None = None,
    diagnostics_service: DependencyDiagnosticsService | None = None,
    media_url_validator: MediaUrlValidationService | None = None,
) -> FastAPI:
    """Create an isolated API application instance."""
    runtime_settings = settings or Settings.from_environment()
    runtime_diagnostics = diagnostics_service or DependencyDiagnosticsService()
    runtime_media_url_validator = media_url_validator or MediaUrlValidationService()
    docs_url = "/docs" if runtime_settings.docs_enabled else None
    openapi_url = "/openapi.json" if runtime_settings.docs_enabled else None

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        application.state.system_diagnostics = runtime_diagnostics.inspect()
        application.state.media_url_validator = runtime_media_url_validator
        yield

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
    return application


app = create_app()
