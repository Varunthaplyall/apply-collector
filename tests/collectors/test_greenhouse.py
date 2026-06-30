"""Tests for Greenhouse async collector — mocked HTTP responses."""

import pytest

from data_collection.collectors.greenhouse_async import AsyncGreenhouseCollector
from data_collection.models import JobPosting


GREENHOUSE_JOBS = [
    {
        "id": 12345,
        "title": "Senior Backend Engineer",
        "absolute_url": "https://boards.greenhouse.io/stripe/jobs/12345",
        "location": {"name": "Bangalore, India"},
        "content": {},
        "departments": [{"name": "Engineering"}],
        "updated_at": "2026-06-15T10:00:00Z",
    },
    {
        "id": 12346,
        "title": "Staff Engineer",
        "absolute_url": "https://boards.greenhouse.io/stripe/jobs/12346",
        "location": {"name": "San Francisco, CA"},
        "content": {},
        "departments": [{"name": "Engineering"}],
        "updated_at": "2026-06-14T10:00:00Z",
    },
]


class TestGreenhouseCollector:
    """Unit tests for Greenhouse job parsing."""

    def test_parse_creates_job_postings(self):
        collector = AsyncGreenhouseCollector(companies=["testco"])
        jobs = collector._parse_jobs("testco", GREENHOUSE_JOBS)
        assert len(jobs) == 2
        assert all(isinstance(j, JobPosting) for j in jobs)

    def test_parse_sets_source_and_source_id(self):
        collector = AsyncGreenhouseCollector(companies=["testco"])
        jobs = collector._parse_jobs("testco", GREENHOUSE_JOBS)
        assert jobs[0].source.value == "greenhouse"
        # source_id format is {slug}-{job_id}
        assert jobs[0].source_id == "testco-12345"
        assert jobs[0].url == "https://boards.greenhouse.io/stripe/jobs/12345"

    def test_parse_extracts_company_from_slug(self):
        collector = AsyncGreenhouseCollector(companies=["stripe"])
        jobs = collector._parse_jobs("stripe", [GREENHOUSE_JOBS[0]])
        assert jobs[0].company == "Stripe"

    def test_parse_skips_jobs_without_id(self):
        collector = AsyncGreenhouseCollector(companies=["testco"])
        jobs = collector._parse_jobs("testco", [{"title": "No ID", "absolute_url": "http://x.com"}])
        assert len(jobs) == 0

    def test_parse_handles_empty_list(self):
        collector = AsyncGreenhouseCollector(companies=["testco"])
        jobs = collector._parse_jobs("testco", [])
        assert jobs == []

    def test_parse_handles_content_as_string(self):
        """Content can be a string (when ?content=true is used)."""
        collector = AsyncGreenhouseCollector(companies=["testco"])
        raw = [{
            "id": 1,
            "title": "Engineer",
            "absolute_url": "https://x.com",
            "location": {"name": "Remote"},
            "content": "Job description here",
            "updated_at": "2026-06-15T10:00:00Z",
        }]
        jobs = collector._parse_jobs("testco", raw)
        assert len(jobs) == 1
        assert "Job description here" in jobs[0].description


class TestGreenhouseSlugLoading:
    """Slug loading logic — no network calls."""

    def test_collector_initializes_with_custom_companies(self):
        collector = AsyncGreenhouseCollector(companies=["stripe", "figma"])
        assert collector.companies == ["stripe", "figma"]

    def test_source_name_is_greenhouse(self):
        collector = AsyncGreenhouseCollector(companies=["test"])
        assert collector.source_name == "greenhouse"
