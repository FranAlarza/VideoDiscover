"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create an isolated API application instance."""
    runtime_settings = settings or Settings.from_environment()
    docs_url = "/docs" if runtime_settings.docs_enabled else None
    openapi_url = "/openapi.json" if runtime_settings.docs_enabled else None

    application = FastAPI(
        title=runtime_settings.app_name,
        docs_url=docs_url,
        redoc_url=None,
        openapi_url=openapi_url,
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
    return application


app = create_app()
