"""Main entry point for the PaperTrail FastAPI application."""

from http import HTTPStatus
from pathlib import Path
import sys
from typing import Any

# Ensure backend/.venv site-packages is in sys.path if launched without activating .venv
_backend_root = Path(__file__).resolve().parent.parent
_venv_site_packages = _backend_root / ".venv" / "Lib" / "site-packages"
if _venv_site_packages.exists() and str(_venv_site_packages) not in sys.path:
    sys.path.insert(0, str(_venv_site_packages))

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.analysis import router as analysis_router
from app.api.documents import router as documents_router
from app.api.llm import router as llm_router
from app.api.papers import router as papers_router
from app.api.projects import router as projects_router
from app.api.routes import router as api_router
from app.config import ALLOWED_ORIGINS, APP_NAME, APP_VERSION
from app.schemas import ErrorResponse


def _status_phrase(status_code: int) -> str:
    """Resolve an HTTP status code to its standard phrase."""
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "Error"


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    application = FastAPI(
        title=f"{APP_NAME} API",
        version=APP_VERSION,
        description="Backend API for the PaperTrail AI research analysis platform.",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        _request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        payload = ErrorResponse(
            error=_status_phrase(exc.status_code),
            message=str(exc.detail),
            status_code=exc.status_code,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=payload.model_dump(exclude_none=True),
        )

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details: list[dict[str, Any]] = [
            {
                "loc": list(err.get("loc", ())),
                "msg": str(err.get("msg", "")),
                "type": str(err.get("type", "")),
            }
            for err in exc.errors()
        ]
        payload = ErrorResponse(
            error="Unprocessable Entity",
            message="Request validation failed.",
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            details=details,
        )
        return JSONResponse(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content=payload.model_dump(exclude_none=True),
        )

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(
        _request: Request, _exc: Exception
    ) -> JSONResponse:
        payload = ErrorResponse(
            error="Internal Server Error",
            message="An unexpected error occurred on the server.",
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        )
        return JSONResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content=payload.model_dump(exclude_none=True),
        )

    application.include_router(api_router)
    application.include_router(papers_router)
    application.include_router(documents_router)
    application.include_router(projects_router)
    application.include_router(llm_router)
    application.include_router(analysis_router)

    return application


app = create_app()
