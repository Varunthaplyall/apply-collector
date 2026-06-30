"""
Shared Pydantic models for the job pipeline.
All collectors produce JobPosting instances; normalizer consumes them.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class JobSource(str, Enum):
    LINKEDIN = "linkedin"
    REMOTIVE = "remotive"
    ADZUNA = "adzuna"
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    WORKDAY = "workday"
    CUTSHORT = "cutshort"
    REMOTEOK = "remoteok"
    ARBEITNOW = "arbeitnow"
    HIMALAYAS = "himalayas"
    YC_JOBS = "yc_jobs"


class JobPosting(BaseModel):
    """Normalized job posting — every collector returns these."""

    source: JobSource
    source_id: str = Field(description="Unique ID from the source (url hash if none)")
    title: str
    company: str
    location: str = ""
    url: str
    description: str = ""
    salary_range: Optional[str] = None
    posted_at: Optional[datetime] = None
    scraped_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def dedup_key(self) -> str:
        return f"{self.title.strip().lower()}|{self.company.strip().lower()}|{self.location.strip().lower()}"
