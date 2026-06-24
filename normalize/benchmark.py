"""
Comprehensive benchmark script for the job aggregator.
Produces BENCHMARK.md with per-source breakdown, coverage analysis,
role/category breakdown, and dedup effectiveness.
"""

import json
import re
import time
from collections import Counter
from datetime import datetime

from data_collection.config import DB_PATH, CONFIG_PATH
from data_collection.database import get_connection


def get_source_breakdown(conn):
    rows = conn.execute("""
        SELECT
            source,
            COUNT(*) as total,
            COUNT(DISTINCT dedup_key) as unique_dedup_key,
            SUM(is_india) as india_count,
            COUNT(*) - SUM(is_india) as non_india,
            MIN(posted_at) as oldest_posting,
            MAX(posted_at) as newest_posting,
            MAX(scraped_at) as last_scraped
        FROM jobs
        GROUP BY source
        ORDER BY total DESC
    """).fetchall()

    results = []
    for row in rows:
        results.append({
            "source": row["source"],
            "total": row["total"],
            "unique_dedup_key": row["unique_dedup_key"],
            "india_count": row["india_count"],
            "non_india": row["non_india"],
            "oldest_posting": row["oldest_posting"] or "N/A",
            "newest_posting": row["newest_posting"] or "N/A",
            "last_scraped": row["last_scraped"] or "N/A",
        })
    return results


def get_company_breakdown(conn, source):
    rows = conn.execute("""
        SELECT
            company,
            COUNT(*) as total,
            SUM(is_india) as india_count,
            MAX(posted_at) as newest_posting
        FROM jobs
        WHERE source = ?
        GROUP BY company
        ORDER BY total DESC
    """, (source,)).fetchall()
    return [dict(row) for row in rows]


def get_coverage_analysis(conn):
    gh_companies = conn.execute(
        "SELECT DISTINCT company FROM jobs WHERE source = 'greenhouse'"
    ).fetchall()
    gh_slugs_in_db = len(gh_companies)

    lever_companies = conn.execute(
        "SELECT DISTINCT company FROM jobs WHERE source = 'lever'"
    ).fetchall()
    lever_slugs_in_db = len(lever_companies)

    with open(CONFIG_PATH) as f:
        config = json.load(f)

    gh_in_config = sum(1 for c in config["companies"] if c.get("ats") == "greenhouse")
    lever_in_config = sum(1 for c in config["companies"] if c.get("ats") == "lever")

    from data_collection.collectors.greenhouse import GreenhouseCollector
    gh_default_count = len(GreenhouseCollector.DEFAULT_COMPANIES)

    return {
        "gh_in_config": gh_in_config,
        "gh_in_defaults": gh_default_count,
        "gh_unique_in_db": gh_slugs_in_db,
        "lever_in_config": lever_in_config,
        "lever_in_defaults": 3,
        "lever_unique_in_db": lever_slugs_in_db,
        "total_gh_universe": 4000,
        "total_lever_universe": 5000,
        "gh_coverage_pct": (gh_slugs_in_db / 4000 * 100),
        "lever_coverage_pct": (lever_slugs_in_db / 5000 * 100),
    }


ROLE_KEYWORDS = {
    "Engineering": [
        "engineer", "developer", "software", "backend", "frontend", "full stack",
        "fullstack", "devops", "sre", "infrastructure", "architect", "programmer",
        "golang", "python", "java ", "javascript", "typescript", "rust",
        "c++", "ruby", "scala", "kotlin", "swift", "react", "node ", "angular",
        "vue", "django", "flask", "spring", "rails", "microservice",
        "cloud", "kubernetes", "docker", "terraform", "aws", "azure", "gcp",
        "platform", "data engineer", "ml engineer", "machine learning engineer",
        "systems engineer", "network engineer", "security engineer", "consulting engineer",
        ".net", "dot net", "android", "ios ", "mobile",
    ],
    "Data / ML / AI": [
        "data scientist", "data analyst", "machine learning", "deep learning",
        "nlp", "computer vision", " ai ", "artificial intelligence", " ml ",
        "analytics", "data platform", "data infra", "mlops", "data architect",
    ],
    "Product": [
        "product manager", "product designer", "product owner",
        "product management", "product lead", "head of product", "vp product",
    ],
    "Design": [
        "designer", " ux ", " ui ", "user experience", "user interface",
        "visual design", "graphic design", "motion design", "brand design",
        "illustration", "creative director",
    ],
    "Sales / BD": [
        "sales", "business development", "account executive", "account manager",
        "bdr", "sdr", "revenue", "partnerships", "enterprise",
    ],
    "Marketing": [
        "marketing", "growth", "seo", "content strategist", "social media",
        "demand generation", "product marketing", "digital marketing",
    ],
    "Operations / Support": [
        "operations", "customer success", "customer support", "support engineer",
        "technical support",
    ],
    "HR / Finance / Legal": [
        "recruiter", "talent", " hr ", "human resources", "finance",
        "accounting", "legal", "counsel", "compliance",
    ],
    "QA / Testing": [
        " qa ", "quality assurance", "test engineer", "sdet", "automation tester",
        "quality analyst", "tester",
    ],
}


def classify_role(title):
    title_lower = " " + title.lower() + " "
    for category, keywords in ROLE_KEYWORDS.items():
        for kw in keywords:
            if kw in title_lower:
                return category
    return "Other"


def get_role_breakdown(conn):
    titles = conn.execute("SELECT title FROM jobs").fetchall()
    categories = Counter()
    for row in titles:
        cat = classify_role(row["title"])
        categories[cat] += 1
    return dict(categories.most_common())


def get_dedup_stats(conn):
    total = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    unique_dedup = conn.execute("SELECT COUNT(DISTINCT dedup_key) FROM jobs").fetchone()[0]
    exact_dupes = total - unique_dedup

    collision_rows = conn.execute("""
        SELECT dedup_key, COUNT(*) as cnt
        FROM jobs
        GROUP BY dedup_key
        HAVING cnt > 1
    """).fetchall()

    collision_count = len(collision_rows)
    total_collision_jobs = sum(row["cnt"] for row in collision_rows)

    from normalize.dedup import normalize_title, normalize_location
    all_jobs = conn.execute("SELECT title, company, location FROM jobs").fetchall()

    fuzzy_keys = set()
    fuzzy_dupes = 0
    for row in all_jobs:
        title = normalize_title(row["title"])
        company = row["company"].lower().strip()
        location = normalize_location(row["location"])
        fkey = f"{title}|{company}|{location}"
        if fkey in fuzzy_keys:
            fuzzy_dupes += 1
        fuzzy_keys.add(fkey)

    return {
        "total_jobs": total,
        "unique_dedup_key": unique_dedup,
        "exact_dupes": exact_dupes,
        "exact_dedup_rate_pct": (exact_dupes / total * 100) if total else 0,
        "collision_groups": collision_count,
        "total_collision_jobs": total_collision_jobs,
        "fuzzy_unique": len(fuzzy_keys),
        "fuzzy_dupes_caught": fuzzy_dupes,
        "fuzzy_dedup_rate_pct": (fuzzy_dupes / total * 100) if total else 0,
    }


def get_freshness_stats(conn):
    rows = conn.execute("""
        SELECT source,
               MAX(posted_at) as newest_posting,
               MIN(posted_at) as oldest_posting,
               COUNT(CASE WHEN posted_at IS NOT NULL
                           AND posted_at::date >= CURRENT_DATE - INTERVAL '7 days'
                          THEN 1 END) as last_7d,
               COUNT(CASE WHEN posted_at IS NOT NULL
                           AND posted_at::date >= CURRENT_DATE - INTERVAL '30 days'
                          THEN 1 END) as last_30d,
               COUNT(CASE WHEN posted_at IS NOT NULL THEN 1 END) as has_date
        FROM jobs
        GROUP BY source
    """).fetchall()
    return [dict(row) for row in rows]


def get_india_city_breakdown(conn):
    rows = conn.execute("""
        SELECT location, COUNT(*) as cnt
        FROM jobs
        WHERE is_india = 1
        GROUP BY location
        ORDER BY cnt DESC
        LIMIT 30
    """).fetchall()
    return [dict(row) for row in rows]


def generate_markdown_report(
    source_breakdown, company_breakdowns, coverage,
    role_breakdown, dedup_stats, freshness, india_cities, run_time,
):
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    total = sum(s["total"] for s in source_breakdown)
    total_india = sum(s["india_count"] for s in source_breakdown)
    total_unique = sum(s["unique_dedup_key"] for s in source_breakdown)

    lines = []
    lines.append("# Job Aggregator Benchmark Report")
    lines.append("")
    lines.append(f"**Generated:** {now}")
    lines.append(f"**Collection run time:** {run_time:.1f}s")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| Total jobs (raw) | {total:,} |")
    lines.append(f"| Unique jobs (dedup_key) | {total_unique:,} |")
    lines.append(f"| India jobs | {total_india:,} |")
    lines.append(f"| Non-India jobs | {total - total_india:,} |")
    lines.append(f"| Sources active | {len([s for s in source_breakdown if s['total'] > 0])} |")
    lines.append(f"| Greenhouse companies in DB | {coverage['gh_unique_in_db']} |")
    lines.append(f"| Lever companies in DB | {coverage['lever_unique_in_db']} |")
    lines.append(f"| Workday tenants | {coverage.get('workday_tenants', 0)} |")
    lines.append("")

    # === Per-source breakdown ===
    lines.append("## 1. Per-Source Breakdown")
    lines.append("")
    lines.append("| Source | Total | Unique | India | Non-India | Newest Posting | Last Scraped |")
    lines.append("|---|---|---|---|---|---|---|")
    for s in source_breakdown:
        newest = str(s["newest_posting"])[:10] if s["newest_posting"] != "N/A" else "N/A"
        scraped = str(s["last_scraped"])[:19] if s["last_scraped"] != "N/A" else "N/A"
        lines.append(
            f"| {s['source']} | {s['total']:,} | {s['unique_dedup_key']:,} | "
            f"{s['india_count']:,} | {s['non_india']:,} | {newest} | {scraped} |"
        )
    lines.append("")

    # Per-company breakdown for top sources
    for source in ["greenhouse", "workday", "lever", "cutshort", "remotive"]:
        companies = company_breakdowns.get(source, [])
        if not companies:
            continue
        lines.append(f"### {source.title()} — Top Companies")
        lines.append("")
        lines.append("| Company | Jobs | India | Newest Posting |")
        lines.append("|---|---|---|---|")
        for c in companies[:25]:
            newest = str(c["newest_posting"])[:10] if c["newest_posting"] else "N/A"
            lines.append(f"| {c['company']} | {c['total']:,} | {c['india_count']} | {newest} |")
        if len(companies) > 25:
            lines.append(f"| *{len(companies) - 25} more companies* | ... | ... | ... |")
        lines.append("")

    # === Coverage analysis ===
    lines.append("## 2. Coverage Analysis")
    lines.append("")
    lines.append("| ATS | In Config | In Defaults | Unique in DB | Est. Universe | Coverage % |")
    lines.append("|---|---|---|---|---|---|")
    lines.append(
        f"| Greenhouse | {coverage['gh_in_config']} | {coverage['gh_in_defaults']} | "
        f"{coverage['gh_unique_in_db']} | ~{coverage['total_gh_universe']:,} | "
        f"{coverage['gh_coverage_pct']:.1f}% |"
    )
    lines.append(
        f"| Lever | {coverage['lever_in_config']} | {coverage['lever_in_defaults']} | "
        f"{coverage['lever_unique_in_db']} | ~{coverage['total_lever_universe']:,} | "
        f"{coverage['lever_coverage_pct']:.1f}% |"
    )
    lines.append("")
    lines.append("*Note: Universe estimates based on public lists of companies using each ATS.*")
    lines.append("*Greenhouse: ~4,000 companies per their public board listings.*")
    lines.append("*Lever: ~5,000 companies per lever.co public postings index.*")
    lines.append("")

    # === Role/category breakdown ===
    lines.append("## 3. Role / Category Breakdown")
    lines.append("")
    lines.append("*Simple keyword classifier on job title — not the real Stage 3 classifier.*")
    lines.append("")
    lines.append("| Category | Jobs | % of Total |")
    lines.append("|---|---|---|")
    for cat, count in role_breakdown.items():
        pct = count / total * 100 if total else 0
        lines.append(f"| {cat} | {count:,} | {pct:.1f}% |")
    lines.append("")

    # === Dedup effectiveness ===
    lines.append("## 4. Dedup Effectiveness")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| Total raw jobs | {dedup_stats['total_jobs']:,} |")
    lines.append(f"| Unique (dedup_key) | {dedup_stats['unique_dedup_key']:,} |")
    lines.append(f"| Exact duplicates | {dedup_stats['exact_dupes']:,} ({dedup_stats['exact_dedup_rate_pct']:.1f}%) |")
    lines.append(f"| Collision groups | {dedup_stats['collision_groups']:,} |")
    lines.append(f"| Jobs in collision groups | {dedup_stats['total_collision_jobs']:,} |")
    lines.append(f"| Fuzzy unique keys | {dedup_stats['fuzzy_unique']:,} |")
    lines.append(f"| Additional fuzzy dupes caught | {dedup_stats['fuzzy_dupes_caught']:,} ({dedup_stats['fuzzy_dedup_rate_pct']:.1f}%) |")
    lines.append("")

    # === Freshness ===
    lines.append("## 5. Freshness Check")
    lines.append("")
    lines.append("| Source | Newest Posting | Oldest Posting | Last 7d | Last 30d | Has Date |")
    lines.append("|---|---|---|---|---|---|")
    for f in freshness:
        newest = str(f["newest_posting"])[:10] if f["newest_posting"] else "N/A"
        oldest = str(f["oldest_posting"])[:10] if f["oldest_posting"] else "N/A"
        lines.append(
            f"| {f['source']} | {newest} | {oldest} | "
            f"{f['last_7d']} | {f['last_30d']} | {f['has_date']} |"
        )
    lines.append("")

    # === India city breakdown ===
    lines.append("## 6. India City Breakdown")
    lines.append("")
    lines.append("| Location | Jobs |")
    lines.append("|---|---|")
    for city in india_cities[:20]:
        loc = city["location"] or "(empty)"
        lines.append(f"| {loc} | {city['cnt']} |")
    lines.append("")

    return "\n".join(lines)


def main():
    conn = get_connection()
    start = time.time()

    print("Running benchmark...")

    source_breakdown = get_source_breakdown(conn)
    print(f"  Sources: {len(source_breakdown)}")

    company_breakdowns = {}
    for s in source_breakdown:
        company_breakdowns[s["source"]] = get_company_breakdown(conn, s["source"])

    coverage = get_coverage_analysis(conn)
    wd_tenants = conn.execute(
        "SELECT COUNT(DISTINCT company) FROM jobs WHERE source = 'workday'"
    ).fetchone()[0]
    coverage["workday_tenants"] = wd_tenants
    print(f"  Greenhouse companies: {coverage['gh_unique_in_db']}")
    print(f"  Lever companies: {coverage['lever_unique_in_db']}")
    print(f"  Workday tenants: {wd_tenants}")

    role_breakdown = get_role_breakdown(conn)
    print(f"  Role categories: {len(role_breakdown)}")

    dedup_stats = get_dedup_stats(conn)
    print(f"  Total jobs: {dedup_stats['total_jobs']}")
    print(f"  Dedup rate: {dedup_stats['exact_dedup_rate_pct']:.1f}%")

    freshness = get_freshness_stats(conn)
    india_cities = get_india_city_breakdown(conn)

    run_time = time.time() - start

    report = generate_markdown_report(
        source_breakdown, company_breakdowns, coverage,
        role_breakdown, dedup_stats, freshness, india_cities, run_time,
    )

    with open("BENCHMARK.md", "w") as f:
        f.write(report)

    print(f"\nBENCHMARK.md generated ({len(report)} chars)")
    conn.close()


if __name__ == "__main__":
    main()
