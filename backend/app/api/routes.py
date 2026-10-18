"""System API routes for health and version checks."""

from fastapi import APIRouter

from app.config import APP_NAME, APP_VERSION
from app.schemas import HealthResponse, VersionResponse

router = APIRouter(prefix="/api", tags=["system"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Returns the operational status of the PaperTrail backend.",
)
async def get_health() -> HealthResponse:
    """Return service health status."""
    return HealthResponse(status="ok", application=APP_NAME)


@router.get(
    "/version",
    response_model=VersionResponse,
    summary="Application Version",
    description="Returns the current version of the PaperTrail backend.",
)
async def get_version() -> VersionResponse:
    """Return application name and version."""
    return VersionResponse(application=APP_NAME, version=APP_VERSION)
