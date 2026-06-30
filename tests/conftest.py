"""Pytest configuration and shared fixtures."""

import pytest

from data_collection.config import DATABASE_URL


@pytest.fixture
def sample_job_data() -> dict:
    """Minimal valid job posting dict for model tests."""
    return {
        "source": "greenhouse",
        "source_id": "gh-12345",
        "title": "Senior Software Engineer",
        "company": "Stripe",
        "location": "Bengaluru, India",
        "url": "https://boards.greenhouse.io/stripe/jobs/12345",
        "description": "Build payment infrastructure.",
        "salary_range": None,
        "posted_at": "2026-06-15T10:00:00",
        "scraped_at": "2026-07-01T12:00:00",
    }


@pytest.fixture
def db_required() -> bool:
    """Skip tests that need a live database when DATABASE_URL is not configured.

    Set to True via pytest.mark.skipif in individual tests.
    """
    return bool(DATABASE_URL)
