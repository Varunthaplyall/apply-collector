"""Tests for Remotive async collector — parsing logic."""

import pytest

from data_collection.collectors.remotive_async import AsyncRemotiveCollector
from data_collection.models import JobPosting


REMOTIVE_RAW_JOB = {
    "id": 789,
    "url": "https://remotive.com/remote-jobs/engineering/789",
    "title": "Senior Python Developer",
    "company_name": "Supabase",
    "category": "Software Development",
    "job_type": "full_time",
    "candidate_required_location": "Worldwide",
    "description": "<p>Build the future of databases.</p>",
    "salary": "$120k - $150k",
    "publication_date": "2026-06-28T10:00:00Z",
}


def _make_response(jobs: list) -> dict:
    """Wrap a list of job dicts into a Remotive API response."""
    return {"job-count": len(jobs), "jobs": jobs}


class TestRemotiveParsing:
    """Unit tests for Remotive job parsing."""

    def test_parse_single_job(self):
        collector = AsyncRemotiveCollector()
        jobs = collector._parse_jobs(_make_response([REMOTIVE_RAW_JOB]))
        assert len(jobs) == 1
        assert isinstance(jobs[0], JobPosting)

    def test_parse_sets_source_fields(self):
        collector = AsyncRemotiveCollector()
        jobs = collector._parse_jobs(_make_response([REMOTIVE_RAW_JOB]))
        job = jobs[0]
        assert job.source.value == "remotive"
        assert job.source_id == "remotive-789"

    def test_parse_sets_title_company(self):
        collector = AsyncRemotiveCollector()
        jobs = collector._parse_jobs(_make_response([REMOTIVE_RAW_JOB]))
        job = jobs[0]
        assert job.title == "Senior Python Developer"
        assert job.company == "Supabase"

    def test_parse_handles_empty_list(self):
        collector = AsyncRemotiveCollector()
        jobs = collector._parse_jobs(_make_response([]))
        assert jobs == []

    def test_parse_skips_jobs_without_id(self):
        collector = AsyncRemotiveCollector()
        jobs = collector._parse_jobs(_make_response([{"title": "Test", "company_name": "TestCo"}]))
        assert len(jobs) == 0

    def test_parse_handles_missing_fields(self):
        collector = AsyncRemotiveCollector()
        jobs = collector._parse_jobs(_make_response([{"id": 1}]))
        assert len(jobs) == 1
        job = jobs[0]
        assert job.title == ""
        assert job.company == ""

    def test_parse_strips_html_from_description(self):
        collector = AsyncRemotiveCollector()
        jobs = collector._parse_jobs(_make_response([REMOTIVE_RAW_JOB]))
        description = jobs[0].description
        assert "Build the future" in description

    def test_parse_dedup_key_is_stable(self):
        collector = AsyncRemotiveCollector()
        jobs1 = collector._parse_jobs(_make_response([REMOTIVE_RAW_JOB]))
        jobs2 = collector._parse_jobs(_make_response([REMOTIVE_RAW_JOB]))
        assert jobs1[0].dedup_key == jobs2[0].dedup_key

    def test_source_name(self):
        collector = AsyncRemotiveCollector()
        assert collector.source_name == "remotive"
