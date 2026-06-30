"""Tests for the FastAPI application endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Patch before importing app to avoid API key errors at import time ──
_mp1 = patch("backend.agents.base_agent.AsyncOpenAI")
_mp1.start()
_mp2 = patch("backend.memory.semantic_memory.AsyncOpenAI")
_mp2.start()

from fastapi.testclient import TestClient

from backend.main import app
from backend.models.db import get_session
from backend.models.schemas import Report, ReviewResponse


# ──────────────────────────────────────────────
#  Fixtures: override FastAPI dependencies
# ──────────────────────────────────────────────


@pytest.fixture
def client():
    """Return a TestClient for the FastAPI app."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def override_deps():
    """Override all FastAPI dependencies to use mocks."""
    mock_session = MagicMock()
    mock_session.execute = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=None)
    mock_scalars = MagicMock()
    mock_scalars.all = MagicMock(return_value=[])
    mock_result.scalars = MagicMock(return_value=mock_scalars)
    mock_result.all = MagicMock(return_value=[])
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    async def override_get_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_get_session
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def mock_orchestrator():
    """Mock the global orchestrator instance."""
    mock_orch = MagicMock()
    mock_report = Report(
        findings=[],
        summary="Test summary",
        rounds=3,
        participants=["security", "architecture", "quality", "performance", "ux"],
        session_id="ses-mock-001",
    )
    mock_orch.run_council = AsyncMock(
        return_value=(
            mock_report,
            "ses-mock-001",
            {"round1": {}, "round2": {}, "round3": {}, "report": {}},
        )
    )
    with patch("backend.main.orchestrator", mock_orch):
        yield mock_orch


@pytest.fixture(autouse=True)
def mock_check_db():
    """Mock check_db_connection to avoid real DB calls."""
    with patch("backend.main.check_db_connection", new=AsyncMock(return_value=False)):
        yield


# ──────────────────────────────────────────────
#  Health endpoint
# ──────────────────────────────────────────────


class TestHealthEndpoint:
    """Tests for GET /api/health."""

    def test_health_returns_ok(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["version"] == "1.0.0"
        assert "db_connected" in data

    def test_health_db_not_connected(self, client):
        response = client.get("/api/health")
        data = response.json()
        assert data["db_connected"] is False


# ──────────────────────────────────────────────
#  Review endpoint
# ──────────────────────────────────────────────


class TestReviewEndpoint:
    """Tests for POST /api/review."""

    def test_review_with_valid_code(self, client):
        """POST /api/review with valid code returns a successful response."""
        response = client.post(
            "/api/review",
            json={"code": "def foo(): pass"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "ses-mock-001"
        assert "report" in data
        assert data["report"]["summary"] == "Test summary"

    def test_review_with_session_id(self, client):
        """POST /api/review with an existing session_id works."""
        response = client.post(
            "/api/review",
            json={"code": "def foo(): pass", "session_id": "ses-existing"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "ses-mock-001"

    def test_review_empty_code_returns_422(self, client):
        """POST /api/review with empty code returns validation error."""
        response = client.post(
            "/api/review",
            json={"code": ""},
        )
        assert response.status_code == 422

    def test_review_missing_code_returns_422(self, client):
        """POST /api/review without code returns validation error."""
        response = client.post(
            "/api/review",
            json={},
        )
        assert response.status_code == 422

    def test_review_with_large_code(self, client):
        """POST /api/review with a large code block still works."""
        large_code = "\n".join([f"line_{i}: pass" for i in range(1000)])
        response = client.post(
            "/api/review",
            json={"code": large_code},
        )
        assert response.status_code == 200

    def test_review_orchestrator_failure_returns_500(self, client, mock_orchestrator):
        """When the orchestrator raises an exception, return 500."""
        mock_orchestrator.run_council = AsyncMock(side_effect=RuntimeError("API down"))
        response = client.post(
            "/api/review",
            json={"code": "def foo(): pass"},
        )
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data


# ──────────────────────────────────────────────
#  Sessions endpoint
# ──────────────────────────────────────────────


class TestSessionsEndpoint:
    """Tests for GET /api/sessions."""

    def test_list_sessions_returns_list(self, client):
        response = client.get("/api/sessions")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_sessions_with_limit(self, client):
        response = client.get("/api/sessions?limit=5")
        assert response.status_code == 200

    def test_session_detail_not_found(self, client):
        """GET /api/sessions/{id} for nonexistent session returns 404."""
        response = client.get("/api/sessions/nonexistent")
        assert response.status_code == 404


# ──────────────────────────────────────────────
#  Memory patterns endpoint
# ──────────────────────────────────────────────


class TestMemoryPatternsEndpoint:
    """Tests for GET /api/memory/patterns."""

    def test_list_patterns_returns_list(self, client):
        response = client.get("/api/memory/patterns")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_patterns_with_category(self, client):
        response = client.get("/api/memory/patterns?category=security")
        assert response.status_code == 200


# ──────────────────────────────────────────────
#  CORS
# ──────────────────────────────────────────────


class TestCORS:
    """Tests for CORS middleware configuration."""

    def test_cors_headers_present(self, client):
        response = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers
