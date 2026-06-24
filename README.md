# Apply Collector

Job collection and normalization pipeline — **Stage 1 (collection) + Stage 2 (dedup)** extracted from the full job-apply-pipeline.

Collects job listings from 9+ sources, normalizes them to a common schema, deduplicates, and stores in SQLite.

## Quick Start

```bash
# Setup
cp .env.template .env
pip install -e .
playwright install

# Collect jobs (async, ~19s)
python -m data_collection.run_all_async

# View stats
python -m normalize.cli
python -m normalize.cli list --location india
python -m normalize.cli search "backend engineer"
```

## Sources

| Source | Type | Auth |
|---|---|---|
| Greenhouse | 229 companies, ATS API | None |
| Lever | 31 companies, ATS API | None |
| YC Jobs | HN "Who is hiring?" threads | None |
| Workday | 11 tenants, internal API | None |
| Cutshort | Sitemap + JSON-LD | None |
| RemoteOK | REST API | None |
| Arbeitnow | REST API | None |
| Himalayas | REST API | None |
| Remotive | REST API | None |
| LinkedIn | Guest jobs API | None |
| Adzuna | REST API | API key |
| JSearch | RapidAPI | API key |

## Project Structure

```
data_collection/     — collectors, database, models, orchestrator
normalize/           — dedup engine, CLI dashboard
data/                — SQLite database (gitignored)
```

## Requirements

- Python >= 3.12
- Dependencies: httpx, pydantic, beautifulsoup4, lxml, python-dotenv, playwright
