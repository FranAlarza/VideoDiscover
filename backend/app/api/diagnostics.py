"""Sanitized local dependency diagnostics endpoint."""

from fastapi import APIRouter, Request

from app.models.diagnostics import SystemDiagnostics

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/diagnostics", response_model=SystemDiagnostics)
async def diagnostics(request: Request) -> SystemDiagnostics:
    """Return the dependency snapshot captured during application startup."""
    return request.app.state.system_diagnostics
