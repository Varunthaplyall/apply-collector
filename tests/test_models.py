"""Tests for JobPosting model, JobSource enum, and dedup key generation."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from data_collection.models import JobPosting, JobSource


class TestJobSourceEnum:
    """Enum completeness — all active + dead sources should be enumerable."""

    def test_active_sources_exist(self):
        """Every collector source_name must be a valid JobSource value."""
        active = {
            "arbeitnow", "cutshort", "greenhouse", "himalayas", "jsearch",
            "lever", "linkedin", "remoteok", "remotive", "workday", "yc_jobs",
        }
        existing = {s.value for s in JobSource}
        missing = active - existing
        assert not missing, f"Sources without enum entries: {missing}"

    def test_dead_sources_still_enum_members(self):
        """Dead sources remain in the enum so historical data is queryable."""
        dead = {"adzuna", "wellfound", "iimjobs"}
        existing = {s.value for s in JobSource}
        missing = dead - existing
        assert not missing, f"Historical sources dropped from enum: {missing}"

    def test_all_values_are_strings(self):
        for source in JobSource:
            assert isinstance(source.value, str)


class TestJobPostingValidation:
    """Pydantic model validation rules."""

    def test_minimal_valid_posting(self, sample_job_data):
        job = JobPosting(**sample_job_data)
        assert job.title == "Senior Software Engineer"
        assert job.source == JobSource.GREENHOUSE

    def test_title_is_required(self, sample_job_data):
        data = {**sample_job_data, "title": None}
        with pytest.raises(ValidationError):
            JobPosting(**data)

    def test_company_is_required(self, sample_job_data):
        data = {**sample_job_data, "company": None}
        with pytest.raises(ValidationError):
            JobPosting(**data)

    def test_source_id_is_required(self, sample_job_data):
        data = {**sample_job_data, "source_id": None}
        with pytest.raises(ValidationError):
            JobPosting(**data)

    def test_url_must_be_string(self, sample_job_data):
        data = {**sample_job_data, "url": None}
        with pytest.raises(ValidationError):
            JobPosting(**data)

    def test_empty_location_defaults_to_empty_string(self, sample_job_data):
        data = {**sample_job_data, "location": ""}
        job = JobPosting(**data)
        assert job.location == ""

    def test_empty_description_defaults_to_empty_string(self, sample_job_data):
        data = {**sample_job_data, "description": ""}
        job = JobPosting(**data)
        assert job.description == ""

    def test_source_must_be_valid_enum(self, sample_job_data):
        data = {**sample_job_data, "source": "nonexistent"}
        with pytest.raises(ValidationError):
            JobPosting(**data)

    def test_datetime_fields_accept_iso8601_strings(self, sample_job_data):
        """posted_at and scraped_at are datetime, Pydantic should parse ISO strings."""
        job = JobPosting(**sample_job_data)
        assert isinstance(job.scraped_at, datetime)


class TestDedupKey:
    """Deduplication key generation — critical for global dedup."""

    def test_dedup_key_is_stable(self, sample_job_data):
        """Same inputs produce the same dedup key every time."""
        job1 = JobPosting(**sample_job_data)
        job2 = JobPosting(**sample_job_data)
        assert job1.dedup_key == job2.dedup_key

    def test_dedup_key_changes_with_different_title(self, sample_job_data):
        """Different title should produce different dedup key."""
        job1 = JobPosting(**sample_job_data)
        job2 = JobPosting(**{**sample_job_data, "title": "Junior Developer"})
        assert job1.dedup_key != job2.dedup_key

    def test_dedup_key_changes_with_different_company(self, sample_job_data):
        """Different company should produce different dedup key."""
        job1 = JobPosting(**sample_job_data)
        job2 = JobPosting(**{**sample_job_data, "company": "Google"})
        assert job1.dedup_key != job2.dedup_key

    def test_dedup_key_handles_unicode(self, sample_job_data):
        """Non-ASCII company names should not break dedup key generation."""
        data = {**sample_job_data, "company": "Möbius GmbH", "title": "Entwickler:in"}
        job = JobPosting(**data)
        assert isinstance(job.dedup_key, str)
        assert len(job.dedup_key) > 0

    def test_dedup_key_handles_long_strings(self, sample_job_data):
        """Extremely long titles/companies should not break dedup key."""
        data = {**sample_job_data, "title": "A" * 1000, "company": "B" * 1000}
        job = JobPosting(**data)
        assert isinstance(job.dedup_key, str)
