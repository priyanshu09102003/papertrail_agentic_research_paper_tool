"""Tests for the PaperTrail FastAPI health, version, CORS, and error responses."""

from fastapi.testclient import TestClient

from app import __version__
from app.main import app

client = TestClient(app)


def test_get_health() -> None:
    """Verify GET /api/health returns 200 OK with expected payload."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "application": "PaperTrail",
    }


def test_get_version() -> None:
    """Verify GET /api/version returns 200 OK with the current version."""
    response = client.get("/api/version")
    assert response.status_code == 200
    data = response.json()
    assert data == {
        "application": "PaperTrail",
        "version": __version__,
    }


def test_cors_allows_local_frontend() -> None:
    """Verify CORS headers allow requests from http://localhost:3000."""
    origin = "http://localhost:3000"
    response = client.options(
        "/api/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin


def test_not_found_returns_clear_error_response() -> None:
    """Verify unknown routes return a structured 404 JSON error response."""
    response = client.get("/api/unknown-route")
    assert response.status_code == 404
    data = response.json()
    assert data["error"] == "Not Found"
    assert data["status_code"] == 404
    assert "message" in data
