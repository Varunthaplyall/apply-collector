"""
Workday jobs collector — uses the internal Workday JSON API directly.

Every Workday-powered career page uses the same API endpoint:
  POST /wday/cxs/{company}/{board}/jobs

No auth, no browser needed. Returns structured JSON with all job fields.
Covers Adobe, Microsoft, ServiceNow, Salesforce, HCL, Capgemini, and 400+ more.
"""

import re
from typing import Sequence

import httpx

from data_collection.collectors.base import BaseCollector
from data_collection.models import JobPosting, JobSource


class WorkdayScraper(BaseCollector):
    """Collect jobs from Workday career portals via direct API calls."""

    source_name = JobSource.WORKDAY.value

    COMPANIES: list[dict] = [
        {"name": "Adobe", "domain": "adobe.wd5.myworkdayjobs.com", "tenant": "adobe", "board": "external_experienced"},
        {"name": "Nvidia", "domain": "nvidia.wd5.myworkdayjobs.com", "tenant": "nvidia", "board": "NVIDIAExternalCareerSite"},
        {"name": "Salesforce", "domain": "salesforce.wd12.myworkdayjobs.com", "tenant": "salesforce", "board": "External_Career_Site"},
        {"name": "ServiceNow", "domain": "servicenow.wd5.myworkdayjobs.com", "tenant": "servicenow", "board": "servicenow_careers"},
        {"name": "Capgemini", "domain": "capgemini.wd3.myworkdayjobs.com", "tenant": "capgemini", "board": "Capgemini_Careers"},
        {"name": "HCL", "domain": "hcl.wd12.myworkdayjobs.com", "tenant": "hcl", "board": "HCL_External_Career_Site"},
        {"name": "VMware", "domain": "vmware.wd1.myworkdayjobs.com", "tenant": "vmware", "board": "VMware_Careers"},
        {"name": "Microsoft", "domain": "microsoft.wd.myworkdayjobs.com", "tenant": "microsoft", "board": "Microsoft_Careers"},
        {"name": "NetApp", "domain": "netapp.wd5.myworkdayjobs.com", "tenant": "netapp", "board": "NetApp_Careers"},
        {"name": "Splunk", "domain": "splunk.wd5.myworkdayjobs.com", "tenant": "splunk", "board": "Splunk_Careers"},
        {"name": "Intel", "domain": "intel.wd1.myworkdayjobs.com", "tenant": "intel", "board": "External"},
    ]

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Origin": "https://example.com",
        "Referer": "https://example.com/",
    }

    def __init__(
        self,
        companies: list[dict] | None = None,
        limit_per_company: int = 200,
        timeout: float = 20.0,
    ):
        self.companies = companies or self.COMPANIES
        self.limit_per_company = limit_per_company
        self.timeout = timeout

    def _fetch_company_jobs(self, company: dict) -> list[JobPosting]:
        """Fetch all jobs from a single Workday tenant."""
        api_url = (
            f"https://{company['domain']}/wday/cxs/"
            f"{company['tenant']}/{company['board']}/jobs"
        )

        headers = self.HEADERS.copy()
        headers["Origin"] = f"https://{company['domain']}"
        headers["Referer"] = f"https://{company['domain']}/{company['board']}/"

        jobs: list[JobPosting] = []
        offset = 0
        limit = 20

        client = httpx.Client(timeout=self.timeout, headers=headers)

        try:
            while len(jobs) < self.limit_per_company:
                payload = {
                    "limit": limit,
                    "offset": offset,
                    "searchText": "",
                    "filters": {},
                }

                resp = client.post(api_url, json=payload)
                if resp.status_code == 404:
                    self.logger.debug("Workday 404 for %s — wrong API path", company["name"])
                    return []
                if resp.status_code == 403:
                    self.logger.debug("Workday 403 for %s — blocked", company["name"])
                    return []
                resp.raise_for_status()

                data = resp.json()
                raw_jobs = data.get("jobPostings", [])
                total = data.get("total", 0)

                if not raw_jobs:
                    break

                for item in raw_jobs:
                    title = item.get("title", "").strip()
                    if not title:
                        continue

                    external_path = item.get("externalPath", "")
                    url = f"https://{company['domain']}{external_path}" if external_path else ""
                    if url and not url.startswith("http"):
                        url = f"https://{company['domain']}{url}"

                    location = item.get("locationsText", "")

                    # Extract posting ID from bulletFields or item
                    source_id = ""
                    if item.get("bulletFields"):
                        source_id = item["bulletFields"][0]
                    if not source_id:
                        source_id = f"{company['name']}-{title[:60]}"

                    jobs.append(
                        JobPosting(
                            source=JobSource.WORKDAY,
                            source_id=f"wd-{company['name']}-{source_id}",
                            title=title,
                            company=company["name"],
                            location=location,
                            url=url,
                            description="",  # Workday API doesn't include descriptions in list view
                        )
                    )

                offset += limit
                # Workday returns total only on first page; stop when results run out
                if len(raw_jobs) < limit:
                    break

        except httpx.HTTPStatusError as e:
            self.logger.warning(
                "Workday %s: HTTP %d", company["name"], e.response.status_code
            )
        except httpx.TimeoutException:
            self.logger.warning("Workday %s: timeout", company["name"])
        except Exception:
            self.logger.exception("Workday failed: %s", company["name"])
        finally:
            client.close()

        return jobs[: self.limit_per_company]

    def collect(self) -> Sequence[JobPosting]:
        all_jobs: list[JobPosting] = []
        for company in self.companies:
            jobs = self._fetch_company_jobs(company)
            all_jobs.extend(jobs)
            self.logger.info("[Workday] %s: %d jobs", company["name"], len(jobs))

        return all_jobs
