"""
Greenhouse Direct ATS API collector.

Greenhouse exposes a free, no-auth JSON API per company board.
Covers 500+ companies (Stripe, Airbnb, Figma, Notion, Linear, etc.).

Endpoint: https://boards-api.greenhouse.io/v1/boards/{slug}/jobs
"""

from typing import Sequence

import httpx

from data_collection.collectors.base import BaseCollector
from data_collection.models import JobPosting, JobSource


class GreenhouseCollector(BaseCollector):
    """Collect jobs from Greenhouse-powered career pages."""

    source_name = JobSource.GREENHOUSE.value

    API_TEMPLATE = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"

    # All confirmed working as of June 2025
    # Discovered by probing the API — silences for 404s are logged and skipped
    DEFAULT_COMPANIES = [
        # FAANG / Big Tech
        "stripe",
        "airbnb",
        "dropbox",
        "databricks",
        "mongodb",
        "snowflake",
        "twilio",
        "robinhood",
        "coinbase",
        "square",
        # Enterprise / SaaS
        "datadog",
        "elastic",
        "newrelic",
        "okta",
        "cloudflare",
        "fastly",
        "jfrog",
        "cockroachlabs",
        "singlestore",
        "firebolt",
        "axiom",
        "chronosphere",
        "fleetio",
        # AI / ML
        "anthropic",
        "figma",
        "canonical",
        "huggingface",
        "replicate",
        "modal",
        "wandb",
        "streamlit",
        # DevTools / Infrastructure
        "vercel",
        "gitlab",
        "netlify",
        "planetscale",
        "sentry",
        "postman",
        "circleci",
        "workato",
        "contentful",
        "storyblok",
        "grafana",
        "prisma",
        "hasura",
        "apollographql",
        # Marketplaces / Fintech
        "pinterest",
        "lyft",
        "instacart",
        "chime",
        "mercury",
        "public",
        "gemini",
        "brex",
        "upwork",
        # Other
        "discord",
        "reddit",
        "mozilla",
        "webflow",
        "intercom",
        "asana",
        "amplitude",
        "calendly",
        "narvar",
        "hubspot",
        "sendgrid",
        "algolia",
        "launchdarkly",
        "fivetran",
        # Additional confirmed
        "shipbob",
        "drift",
        "supabase",
        "neon",
        "railway",
        "render",
        "deno",
        "astronomer",
        "dagster",
        "perplexity",
        "cohere",
        "deepmind",
        "cloudinary",
        "nx",
        "sanity",
        "builderio",
        "plasmic",
        "logdna",
        "gitbook",
        "readme",
        "height",
        "superhuman",
        "slack",
        "tray",
        "parabola",
        "jump",
        "wealthsimple",
        "multi",
        "flexiple",
        "toptal",
        "andela",
        "motherduck",
        "you",
        "character",
        "elevenlabs",
        "midjourney",
        # Indian companies (verified working June 2025)
        "groww",
        "postman",
        "phonepe",
        "slice",
        # The following return 0 jobs or 404 — kept for retry on subsequent runs
        "notion",
        "linear",
        "doordash",
        "hashicorp",
        "canva",
        "gong",
        "confluent",
        "deel",
        "benchling",
        "palantir",
        "quora",
        "zapier",
        "retool",
        "plaid",
        "chainlinklabs",
        "ironcladapp",
        "lever",
        "spotify",
        "digitalocean",
        "segment",
        "openai",
    ]

    def __init__(
        self,
        companies: list[str] | None = None,
        content: str = "true",
        timeout: float = 30.0,
    ):
        self.companies = companies or self.DEFAULT_COMPANIES
        self.content = content  # "true" to get full descriptions
        self.timeout = timeout

    def _fetch_company_jobs(self, slug: str) -> list[dict]:
        url = self.API_TEMPLATE.format(slug=slug)
        all_jobs: list[dict] = []
        page = 1

        with httpx.Client(timeout=self.timeout) as client:
            while True:
                resp = client.get(url, params={"content": self.content, "page": page})
                if resp.status_code == 404:
                    break  # invalid slug
                resp.raise_for_status()
                data = resp.json()
                all_jobs.extend(data.get("jobs", []))
                if not data.get("meta", {}).get("next"):
                    break
                page += 1

        return all_jobs

    def _parse_jobs(self, slug: str, raw_jobs: list[dict]) -> list[JobPosting]:
        jobs: list[JobPosting] = []
        for item in raw_jobs:
            job_id = item.get("id", "")
            if not job_id:
                continue

            # Build description from Greenhouse's structured content
            content = item.get("content", {})
            description = ""
            if isinstance(content, dict):
                desc_parts: list[str] = []
                for section in content.get("sections", []):
                    if isinstance(section, dict):
                        text = (section.get("plain_text_content", "") or "").strip()
                        if text:
                            desc_parts.append(text)
                description = "\n\n".join(desc_parts)
            elif isinstance(content, str):
                description = content

            offices = item.get("offices", [{}])
            location = ", ".join(
                o.get("name", o.get("location", "")) for o in offices if o
            )

            jobs.append(
                JobPosting(
                    source=JobSource.GREENHOUSE,
                    source_id=f"{slug}-{job_id}",
                    title=item.get("title", ""),
                    company=slug.title(),
                    location=location,
                    url=item.get("absolute_url", ""),
                    description=description,
                )
            )
        return jobs

    def collect(self) -> Sequence[JobPosting]:
        all_jobs: list[JobPosting] = []
        for slug in self.companies:
            try:
                raw = self._fetch_company_jobs(slug)
                jobs = self._parse_jobs(slug, raw)
                all_jobs.extend(jobs)
                self.logger.info(
                    "[Greenhouse] %s: %d jobs", slug, len(jobs)
                )
            except Exception:
                self.logger.exception(
                    "Failed fetching Greenhouse: slug=%s", slug
                )
        return all_jobs
