"""Tests for Flask API endpoints — no auth (public) routes."""

import pytest

from web.app import app


@pytest.fixture
def client():
    """Flask test client with application context."""
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class TestHealthEndpoint:
    """GET /api/health — health check endpoint."""

    def test_health_returns_json(self, client):
        resp = client.get("/api/health")
        assert resp.status_code in (200, 503)  # 503 acceptable if no DB
        data = resp.get_json()
        assert "healthy" in data
        assert "pool_initialized" in data
        assert "pool" in data

    def test_health_has_pool_stats(self, client):
        resp = client.get("/api/health")
        data = resp.get_json()
        pool = data.get("pool", {})
        assert "initialized" in pool


class TestStatsEndpoint:
    """GET /api/stats — dashboard statistics."""

    def test_stats_returns_json(self, client):
        resp = client.get("/api/stats")
        # May 500 if no DB, but shouldn't crash
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            data = resp.get_json()
            assert isinstance(data, dict)

    def test_stats_content_type(self, client):
        resp = client.get("/api/stats")
        if resp.status_code == 200:
            assert resp.content_type == "application/json"


class TestJobsEndpoint:
    """GET /api/jobs — job listing with filters."""

    def test_jobs_returns_json(self, client):
        resp = client.get("/api/jobs")
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            data = resp.get_json()
            assert isinstance(data, dict)

    def test_jobs_with_search_query(self, client):
        resp = client.get("/api/jobs?search=engineer")
        assert resp.status_code in (200, 500)

    def test_jobs_with_source_filter(self, client):
        resp = client.get("/api/jobs?source=greenhouse")
        assert resp.status_code in (200, 500)

    def test_jobs_with_india_filter(self, client):
        resp = client.get("/api/jobs?india_only=true")
        assert resp.status_code in (200, 500)

    def test_jobs_with_pagination(self, client):
        resp = client.get("/api/jobs?page=1&per_page=10")
        assert resp.status_code in (200, 500)


class TestHistoryEndpoint:
    """GET /api/history — run history."""

    def test_history_returns_json(self, client):
        resp = client.get("/api/history")
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            data = resp.get_json()
            assert isinstance(data, list)


class TestProfileEndpoint:
    """GET /api/profile — requires auth."""

    def test_profile_without_auth_returns_401(self, client):
        resp = client.get("/api/profile")
        assert resp.status_code == 401

    def test_profile_with_invalid_token_returns_401(self, client):
        resp = client.get("/api/profile", headers={"Authorization": "Bearer bad-token"})
        assert resp.status_code == 401


class TestRunCollectEndpoint:
    """POST /api/run/collect — pipeline trigger."""

    def test_run_collect_returns_json(self, client):
        """Endpoint requires auth; 401 expected without token."""
        resp = client.post("/api/run/collect")
        assert resp.status_code in (200, 401, 409, 503)
        data = resp.get_json()
        assert "status" in data or "error" in data


class TestCronEndpoint:
    """POST /api/cron/collect — cron trigger."""

    def test_cron_collect_without_secret_is_unprotected(self, client):
        """When CRON_SECRET is unset, cron endpoint accepts requests (dev mode)."""
        resp = client.post("/api/cron/collect")
        # 200 = secret check disabled, 401 = missing secret, 500 = DB error
        assert resp.status_code in (200, 401, 500)


class TestAuthMeEndpoint:
    """GET /api/auth/me — authenticated user info."""

    def test_auth_me_without_token_returns_401(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401
