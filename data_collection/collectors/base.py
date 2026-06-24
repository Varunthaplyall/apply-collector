"""
Base collector class — all job source collectors inherit from this.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Sequence

from data_collection.models import JobPosting

logger = logging.getLogger(__name__)


class BaseCollector(ABC):
    """Base class for all job posting collectors.

    Subclasses must implement:
      - source_name (property)  — JobSource enum value
      - collect()               — return list of JobPosting
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        ...

    @abstractmethod
    def collect(self) -> Sequence[JobPosting]:
        """Fetch job postings from the source. May raise on network failure."""
        ...

    @property
    def logger(self) -> logging.Logger:
        return logging.getLogger(f"{__name__}.{self.source_name}")

    def run(self) -> list[JobPosting]:
        """Wrapper with logging. Called by the orchestrator."""
        self.logger.info("Starting collection ...")
        try:
            results = list(self.collect())
            self.logger.info("Collected %d jobs", len(results))
            return results
        except Exception:
            self.logger.exception("Collection failed")
            raise


class AsyncBaseCollector(ABC):
    """Async version of BaseCollector for concurrent execution."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        ...

    @abstractmethod
    async def collect(self) -> Sequence[JobPosting]:
        """Async fetch job postings from the source."""
        ...

    @property
    def logger(self) -> logging.Logger:
        return logging.getLogger(f"{__name__}.{self.source_name}")

    async def run(self) -> list[JobPosting]:
        """Async wrapper with logging."""
        self.logger.info("Starting async collection ...")
        try:
            results = list(await self.collect())
            self.logger.info("Collected %d jobs", len(results))
            return results
        except Exception:
            self.logger.exception("Async collection failed")
            raise
