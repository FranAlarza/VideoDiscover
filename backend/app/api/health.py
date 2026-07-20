"""Health-check endpoint."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Public response returned by the liveness endpoint."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"] = "ok"
    service: Literal["video-downloader-api"] = "video-downloader-api"


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Report whether the API process can serve requests."""
    return HealthResponse()
