"""
Candidate profile model, CRUD, and job filtering engine.

A profile encodes everything we know about a candidate's preferences —
target roles, skills, salary, location, etc.  The filter engine scores
every job against the active profile and records matches in
profile_job_matches.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional, Sequence

from data_collection.database import get_connection

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────
# Constants / enums
# ──────────────────────────────────────────────────────────────────────────

EXPERIENCE_LEVELS = ["ENTRY", "MID", "SENIOR", "LEAD", "STAFF", "PRINCIPAL"]
WORK_TYPES       = ["FULL_TIME", "CONTRACT", "PART_TIME", "INTERNSHIP", "FREELANCE"]
REMOTE_PREFERENCES = ["REMOTE", "HYBRID", "ON_SITE", "ANY"]
COMPANY_SIZES     = ["STARTUP", "SMALL", "MID", "LARGE", "ENTERPRISE", "ANY"]
EDUCATION_LEVELS  = ["HIGH_SCHOOL", "ASSOCIATES", "BACHELORS", "MASTERS", "PHD", "ANY"]
CURRENCIES        = ["USD", "INR", "EUR", "GBP", "CAD", "AUD"]

# All valid job sources (mirrors JobSource enum from models.py)
ALL_SOURCES = [
    "linkedin", "indeed", "remotive", "adzuna", "greenhouse",
    "lever", "workday", "cutshort", "remoteok", "arbeitnow",
    "himalayas", "yc_jobs", "wellfound", "iimjobs",
]

# ──────────────────────────────────────────────────────────────────────────
# Seniority keyword mapping — used to compare declared level vs job title
# ──────────────────────────────────────────────────────────────────────────

_SENIORITY_PATTERNS: dict[str, list[str]] = {
    "ENTRY": [
        r"\b(junior|jr\.?|associate|entry.level|trainee|intern|graduate|new.grad)",
    ],
    "MID": [
        r"\b(mid.level|mid|intermediate)\b",
    ],
    "SENIOR": [
        r"\b(senior|sr\.?|lead|principal|staff|architect|head.of|director|vp|vice.president)(?:\s|$)",
    ],
}

# Role-to-skill associations for weak-skill matching
_KNOWN_ROLE_SKILLS: dict[str, list[str]] = {
    "backend": ["python", "java", "go", "golang", "rust", "node", "node.js",
                "c#", ".net", "ruby", "rails", "django", "fastapi", "spring",
                "express", "postgresql", "mysql", "mongodb", "redis", "aws",
                "gcp", "azure", "docker", "kubernetes", "graphql", "rest",
                "microservices", "kafka", "rabbitmq"],
    "frontend": ["javascript", "typescript", "react", "angular", "vue", "svelte",
                 "next.js", "html", "css", "tailwind", "webpack", "redux"],
    "full stack": ["python", "javascript", "typescript", "react", "angular",
                   "node", "django", "rails", "postgresql", "aws", "docker"],
    "mobile": ["swift", "kotlin", "java", "react native", "flutter", "dart",
               "ios", "android", "xcode"],
    "data": ["python", "sql", "pytorch", "tensorflow", "pandas", "numpy",
             "spark", "hadoop", "airflow", "dbt", "mlflow", "kafka"],
    "devops": ["aws", "gcp", "azure", "docker", "kubernetes", "terraform",
               "ansible", "jenkins", "github actions", "prometheus", "grafana",
               "linux", "bash", "ci/cd"],
    "security": ["owasp", "penetration.testing", "siem", "soc", "incident.response",
                 "cryptography", "identity", "iam", "compliance"],
    "qa": ["selenium", "cypress", "playwright", "jest", "junit", "pytest",
           "manual.testing", "automation", "regression", "load.testing"],
    "ai/ml": ["pytorch", "tensorflow", "jax", "transformers", "llm", "nlp",
              "computer.vision", "deep.learning", "mlops", "langchain"],
}

# ──────────────────────────────────────────────────────────────────────────
# Title synonym maps — normalizes role titles to canonical forms
# ──────────────────────────────────────────────────────────────────────────

# Maps canonical terms → their synonyms/aliases
_TITLE_SYNONYMS: dict[str, list[str]] = {
    "engineer": ["developer", "programmer", "coder", "engineer"],
    "frontend": ["front end", "front-end", "client side", "client-side", "ui"],
    "backend": ["back end", "back-end", "server side", "server-side"],
    "full stack": ["fullstack", "full-stack", "fullstack"],
    "devops": ["sre", "site reliability", "site.reliability", "platform engineer",
               "infrastructure engineer", "cloud engineer", "release engineer"],
    "mobile": ["android", "ios", "mobile"],
    "data": ["data", "analytics", "etl", "bi", "business intelligence"],
    "embedded": ["firmware", "embedded systems", "iot", "rtos"],
    "solution": ["solutions", "solution"],
    "architect": ["architecture", "architect", "technical architect"],
    "manager": ["manager", "lead", "head", "director", "vp"],
    "consultant": ["consultant", "advisor", "specialist"],
}

# ──────────────────────────────────────────────────────────────────────────
# Skill taxonomy — maps skills to their children/related tech
# ──────────────────────────────────────────────────────────────────────────

_SKILL_TAXONOMY: dict[str, list[str]] = {
    "react": ["react.js", "reactjs", "react native", "next.js", "nextjs",
              "redux", "jsx", "react router", "gatsby", "remix"],
    "angular": ["angular.js", "angularjs", "angular 2", "angular2", "rxjs", "ngrx"],
    "vue": ["vue.js", "vuejs", "nuxt", "vuex", "pinia", "vuetify"],
    "python": ["django", "flask", "fastapi", "pandas", "numpy", "pytest",
               "sqlalchemy", "celery", "pydantic", "poetry"],
    "javascript": ["js", "es6", "ecmascript", "node", "node.js", "nodejs",
                   "typescript", "ts", "bun", "deno"],
    "typescript": ["ts", "typescript", "typeorm", "ts-node", "tsx"],
    "java": ["spring", "spring boot", "springboot", "jvm", "hibernate",
             "jpa", "maven", "gradle", "jakarta", "kotlin"],
    "go": ["golang", "go lang"],
    "aws": ["lambda", "s3", "ec2", "dynamodb", "sqs", "sns", "cloudformation",
            "ecs", "eks", "rds", "cloudfront", "route53", "iam", "cloudwatch",
            "api gateway", "step functions", "fargate", "elasticache",
            "aws", "amazon web services"],
    "gcp": ["google cloud", "gcp", "bigquery", "cloud run", "cloud functions",
            "gke", "pub/sub", "cloud storage", "firestore"],
    "azure": ["microsoft azure", "azure devops", "aks", "azure functions",
              "cosmos db", "azure sql", "entra"],
    "docker": ["docker", "container", "containers", "dockerfile", "docker-compose"],
    "kubernetes": ["k8s", "kubernetes", "helm", "kubectl", "eks", "gke", "aks",
                   "istio", "linkerd", "argocd"],
    "terraform": ["terraform", "terragrunt", "tf", "iac", "infrastructure as code",
                  "opentofu", "pulumi"],
    "postgresql": ["postgres", "postgresql", "psql", "pg", "plpgsql"],
    "mysql": ["mysql", "mariadb", "aurora"],
    "mongodb": ["mongo", "mongodb", "nosql", "documentdb"],
    "redis": ["redis", "elasticache", "valkey"],
    "graphql": ["graphql", "apollo", "relay", "graphql yoga"],
    "kafka": ["kafka", "event streaming", "event bus", "confluent", "redpanda"],
    "ci/cd": ["ci/cd", "ci cd", "continuous integration", "continuous deployment",
              "github actions", "gitlab ci", "jenkins", "circleci", "travis",
              "argocd", "spinnaker", "drone"],
    "machine learning": ["ml", "machine learning", "deep learning", "neural network",
                         "tensorflow", "pytorch", "jax", "scikit-learn", "sklearn",
                         "xgboost", "lightgbm", "transformers", "hugging face",
                         "llm", "nlp", "computer vision", "langchain", "mlops"],
    "rust": ["rust", "cargo", "tokio", "serde", "actix"],
    "c#": ["c#", "csharp", ".net", "dotnet", "asp.net", "blazor", "xamarin",
           "unity", "entity framework"],
    "ruby": ["ruby", "rails", "ruby on rails", "ror", "sinatra", "rspec"],
}

# ──────────────────────────────────────────────────────────────────────────
# Metro area location maps — handles city/region aliases
# ──────────────────────────────────────────────────────────────────────────

_METRO_AREAS: dict[str, list[str]] = {
    "san francisco": ["bay area", "south bay", "sf", "silicon valley",
                      "san jose", "oakland", "palo alto", "mountain view",
                      "menlo park", "sunnyvale", "santa clara", "san mateo",
                      "fremont", "berkeley", "redwood city", "cupertino"],
    "new york": ["nyc", "new york city", "manhattan", "brooklyn", "queens",
                 "bronx", "staten island", "long island", "hoboken", "jersey city"],
    "seattle": ["seattle", "bellevue", "redmond", "kirkland", "renton"],
    "los angeles": ["la", "los angeles", "santa monica", "venice", "culver city",
                    "pasadena", "burbank", "glendale", "long beach", "irvine"],
    "austin": ["austin", "round rock", "cedar park"],
    "boston": ["boston", "cambridge", "somerville", "waltham", "lexington",
               "newton", "brookline"],
    "chicago": ["chicago", "evanston", "naperville", "schaumburg"],
    "denver": ["denver", "boulder", "aurora", "lakewood", "westminster"],
    "bengaluru": ["bangalore", "blr", "electronic city", "whitefield",
                  "bengaluru", "koramangala", "hsr layout", "indiranagar",
                  "marathahalli", "bellandur", "sarjapur", "manyata"],
    "delhi ncr": ["delhi", "ncr", "gurgaon", "gurugram", "noida", "new delhi",
                  "ghaziabad", "faridabad", "delhi ncr", "dwarka", "saket"],
    "mumbai": ["mumbai", "bombay", "navi mumbai", "thane", "powai", "andheri",
               "lower parel", "bandra", "worli", "bkc"],
    "hyderabad": ["hyderabad", "hitech city", "gachibowli", "madhapur",
                  "kondapur", "hitec city", "secunderabad", "cyberabad"],
    "pune": ["pune", "hinjewadi", "magarpatta", "kharadi", "wadgaon sheri",
             "baner", "viman nagar", "kalyani nagar"],
    "chennai": ["chennai", "madras", "omr", "guindy", "taramani", "thoraipakkam",
                "sholinganallur", "adyar", "velachery"],
    "kolkata": ["kolkata", "calcutta", "salt lake", "new town", "rajarhat"],
    "remote": ["remote", "work from home", "wfh", "anywhere", "distributed",
               "work from anywhere", "fully remote", "global remote"],
}

# ──────────────────────────────────────────────────────────────────────────
# Company quality tiers — bonus/penalty for known companies
# ──────────────────────────────────────────────────────────────────────────

# Tier 1: top-tier tech — strong bonus
_COMPANY_TIER_1: set[str] = {
    "google", "facebook", "meta", "apple", "amazon", "microsoft", "netflix",
    "stripe", "airbnb", "uber", "linkedin", "twitter", "x", "dropbox",
    "spotify", "atlassian", "canva", "figma", "notion", "linear", "vercel",
    "databricks", "snowflake", "palantir", "openai", "anthropic", "scale ai",
    "roblox", "square", "block", "plaid", "brex", "rippling", "ramp",
    "doordash", "instacart", "coinbase", "robinhood", "nvidia",
}

# Tier 2: strong mid-tier — moderate bonus
_COMPANY_TIER_2: set[str] = {
    "shopify", "hubspot", "twilio", "gitlab", "github", "slack", "salesforce",
    "adobe", "zoom", "okta", "splunk", "datadog", "mongodb", "confluent",
    "hashicorp", "cloudflare", "fastly", "elastic", "reddit", "pinterest",
    "snap", "discord", "roblox", "epic games", "unity", "lyft", "zillow",
    "chime", "affirm", "sofi", "mercury", "gusto", "deel", "remote",
    "postman", "hasura", "supabase", "neon", "planetscale", "fly.io",
    "railway", "render", "netlify", "tailscale", "clerk", "liveblocks",
    "temporal", "dagger", "warp", "cursor", "replit",
}

# Tier 3: known body shops / WITCH — penalty (already in REJECT in dedup.py)
_COMPANY_TIER_PENALTY: set[str] = {
    "tcs", "tata consultancy", "infosys", "wipro", "hcl", "tech mahindra",
    "cognizant", "accenture", "capgemini", "ibm", "cognizant technology",
    "wipro limited", "hcl technologies", "mphasis", "l&t infotech",
    "lti", "mindtree", "hexaware", "zensar", "cyient", "persistent systems",
    "birlasoft", "sonata software", "niit technologies",
}

# ──────────────────────────────────────────────────────────────────────────
# Experience years parsing regex
# ──────────────────────────────────────────────────────────────────────────

_EXPERIENCE_PATTERNS: list[re.Pattern] = [
    re.compile(r"(\d+)\+?\s*(?:to|-)\s*(\d+)\+?\s*years?\s*(?:of\s*)?experience", re.IGNORECASE),
    re.compile(r"(\d+)\s*[-–]\s*(\d+)\s*years?\s*(?:of\s*)?experience", re.IGNORECASE),
    re.compile(r"at\s+least\s+(\d+)\+?\s*years?\s*(?:of\s*)?experience", re.IGNORECASE),
    re.compile(r"minimum\s+(?:of\s+)?(\d+)\+?\s*years?\s*(?:of\s*)?experience", re.IGNORECASE),
    re.compile(r"(\d+)\+?\s*years?\s*(?:of\s*)?experience\s*(?:is\s*)?required", re.IGNORECASE),
    re.compile(r"experience\s*(?:of\s*)?(\d+)\s*[-–]\s*(\d+)\s*years", re.IGNORECASE),
    re.compile(r"(\d+)\+?\s*years?\s*(?:of\s*)?(?:relevant\s*)?experience", re.IGNORECASE),
]

# ──────────────────────────────────────────────────────────────────────────
# Salary parsing regex
# ──────────────────────────────────────────────────────────────────────────

_SALARY_AMOUNT_PATTERNS = [
    # $100k - $150k, $100,000 - $150,000
    re.compile(r"\$?(\d{2,3}(?:,\d{3})?(?:\.\d+)?)\s*k?\s*(?:-|–|to)\s*\$?(\d{2,3}(?:,\d{3})?(?:\.\d+)?)\s*k?", re.IGNORECASE),
    # ₹10L - ₹20L, ₹10,00,000 - ₹20,00,000
    re.compile(r"₹?(\d{1,2}(?:,\d{2,3})?(?:\.\d+)?)\s*[Ll]?\s*(?:-|–|to)\s*₹?(\d{1,2}(?:,\d{2,3})?(?:\.\d+)?)\s*[Ll]?", re.IGNORECASE),
    # Up to $150k, up to ₹20L
    re.compile(r"up\s+to\s+\$?(\d{2,3}(?:,\d{3})?(?:\.\d+)?)\s*k?", re.IGNORECASE),
    # $100k+, ₹10L+
    re.compile(r"\$?(\d{2,3}(?:,\d{3})?(?:\.\d+)?)\s*k?\s*\+", re.IGNORECASE),
]


# ──────────────────────────────────────────────────────────────────────────
# Scoring utility functions
# ──────────────────────────────────────────────────────────────────────────


def _normalize_title_to_canonical(title: str) -> set[str]:
    """Convert a job title into a set of canonical terms for fuzzy matching.

    Example: "Senior Full-Stack JavaScript Developer"
    → {"senior", "full stack", "engineer", "javascript", "frontend"}
    """
    title_lower = title.lower().strip()
    # Remove parentheticals and location suffixes
    title_lower = re.sub(r"\s*\([^)]*\)", "", title_lower)
    title_lower = re.sub(r"\s*[-–]\s*(remote|hybrid|on.site|on_site)\b", "", title_lower, flags=re.IGNORECASE)

    tokens = _tokenize(title_lower)
    canonical: set[str] = set()

    # Check multi-word synonyms first
    title_clean = re.sub(r"[.\-]+", " ", title_lower)
    title_clean = " ".join(title_clean.split())

    for canonical_term, synonyms in _TITLE_SYNONYMS.items():
        for syn in synonyms:
            # Check for multi-word synonyms
            if " " in syn and syn in title_clean:
                canonical.add(canonical_term)
            elif syn in tokens:
                canonical.add(canonical_term)

    return canonical


def _expand_skills(skills: list[str]) -> set[str]:
    """Expand a skill list to include taxonomy children.

    E.g., ["react"] → {"react", "react.js", "reactjs", "next.js", "redux", ...}
    """
    expanded: set[str] = set()
    for skill in skills:
        skill_lower = skill.lower().strip()
        expanded.add(skill_lower)
        # Check taxonomy
        if skill_lower in _SKILL_TAXONOMY:
            expanded.update(s.lower() for s in _SKILL_TAXONOMY[skill_lower])
    return expanded


def _expand_location(locations: list[str]) -> set[str]:
    """Expand locations to include metro area aliases.

    E.g., ["San Francisco"] → {"san francisco", "bay area", "sf", "san jose", ...}
    """
    expanded: set[str] = set()
    for loc in locations:
        loc_lower = loc.lower().strip()
        expanded.add(loc_lower)
        # Check metro areas
        for metro, aliases in _METRO_AREAS.items():
            if loc_lower == metro or loc_lower in aliases:
                expanded.add(metro)
                expanded.update(a.lower() for a in aliases)
                break
    return expanded


def _parse_experience_years(description: str) -> tuple[int, int] | None:
    """Extract required years of experience from job description text.

    Returns (min_years, max_years) tuple, or None if not found.
    """
    if not description:
        return None

    text = description[:3000]  # only first 3K chars matter for requirements

    for pattern in _EXPERIENCE_PATTERNS:
        m = pattern.search(text)
        if m:
            groups = m.groups()
            if len(groups) == 2 and groups[1]:
                return (int(groups[0]), int(groups[1]))
            elif len(groups) >= 1:
                years = int(groups[0])
                return (years, years + 5)  # assume range up to +5

    return None


def _parse_salary_usd(salary_range: str, currency: str) -> int | None:
    """Extract the midpoint salary in USD-equivalent from a salary range string.

    Very rough estimate — handles common formats.
    """
    if not salary_range:
        return None

    # Try to find the larger number (upper bound of range)
    amounts = re.findall(r"[\d,]+\.?\d*", salary_range.replace(",", ""))
    if not amounts:
        return None

    # Get the largest numeric value
    try:
        nums = [float(a.replace(",", "")) for a in amounts]
    except ValueError:
        return None

    max_num = max(nums)

    # Heuristic: determine the unit based on context
    range_lower = salary_range.lower()

    # Check for lakhs / crores (Indian)
    if "lakh" in range_lower or "lac" in range_lower or "lpa" in range_lower or "₹" in range_lower or "rs" in range_lower:
        # Convert lakhs → USD (rough: 1 lakh INR ≈ $1,200)
        if max_num < 100:  # likely in lakhs
            return int(max_num * 100000 / 83)  # INR to USD
        else:
            return int(max_num / 83)

    # Check for thousands (k)
    if "k" in range_lower or max_num < 1000:
        # e.g., "$150k" means 150,000
        return int(max_num * 1000) if max_num < 1000 else int(max_num)

    # Assume it's already in raw dollars
    return int(max_num)


def _compute_freshness_decay(posted_at: str | None, scraped_at: str | None) -> float:
    """Compute a decay multiplier based on job age. 1.0 = fresh, 0.5 = 90+ days old."""
    from datetime import datetime, timezone

    ref_date = None
    if posted_at:
        try:
            # Try ISO format
            ref_date = datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass

    if ref_date is None and scraped_at:
        try:
            ref_date = datetime.fromisoformat(scraped_at.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass

    if ref_date is None:
        return 1.0  # can't determine age, assume fresh

    now = datetime.now(timezone.utc)
    if ref_date.tzinfo is None:
        ref_date = ref_date.replace(tzinfo=timezone.utc)

    age_days = (now - ref_date).days
    if age_days <= 7:
        return 1.0
    elif age_days <= 30:
        return 0.9
    elif age_days <= 60:
        return 0.75
    elif age_days <= 90:
        return 0.6
    else:
        return 0.5


def _get_dismissed_skill_penalty(profile_id: int, job_skills: set[str]) -> float:
    """Check if the user has previously dismissed jobs with similar skills.

    Returns a penalty multiplier (0.5-1.0). 1.0 = no penalty.
    """
    if not profile_id or not job_skills:
        return 1.0

    try:
        conn = get_connection()
        # Find dismissed jobs for this profile
        dismissed_rows = conn.execute(
            """SELECT j.title, j.description
             FROM profile_job_matches pjm
             JOIN jobs j ON j.id = pjm.job_id
             WHERE pjm.profile_id = ? AND pjm.dismissed = 1""",
            (profile_id,),
        ).fetchall()
        conn.close()

        if not dismissed_rows:
            return 1.0

        # Count how many dismissed jobs share skills with this job
        dismissed_skill_hits = 0
        for row in dismissed_rows:
            desc_lower = (row.get("description") or "").lower()
            title_lower = (row.get("title") or "").lower()
            combined = f"{title_lower} {desc_lower}"
            for skill in job_skills:
                if skill.lower() in combined:
                    dismissed_skill_hits += 1
                    break  # count each dismissed job once

        # If 3+ dismissed jobs share skills, apply penalty
        if dismissed_skill_hits >= 5:
            return 0.5
        elif dismissed_skill_hits >= 3:
            return 0.7
        else:
            return 1.0
    except Exception:
        return 1.0  # fail gracefully


@dataclass
class CandidateProfile:
    """All the preferences a candidate can express."""

    # Database id (0 if not persisted)
    id: int = 0

    # Identity
    name: str = ""
    email: str = ""
    phone: str = ""
    notes: str = ""

    # Target roles (list of strings, e.g. ["Senior Backend Engineer"])
    target_roles: list[str] = field(default_factory=list)

    # Skills (technologies, languages, frameworks)
    skills: list[str] = field(default_factory=list)

    # Experience
    experience_level: str = "MID"              # ENTRY | MID | SENIOR | LEAD | STAFF | PRINCIPAL
    experience_years_min: int = 0
    experience_years_max: int = 15

    # Work arrangements
    work_types: list[str] = field(default_factory=list)          # FULL_TIME | CONTRACT | PART_TIME | INTERNSHIP
    remote_preference: str = "ANY"                                # REMOTE | HYBRID | ON_SITE | ANY

    # Locations
    preferred_locations: list[str] = field(default_factory=list)  # e.g. ["Bengaluru", "Mumbai", "Remote"]

    # Compensation
    min_salary: int | None = None
    salary_currency: str = "USD"

    # Domain / industry
    preferred_industries: list[str] = field(default_factory=list)

    # Keyword filters
    include_keywords: list[str] = field(default_factory=list)
    exclude_keywords: list[str] = field(default_factory=list)

    # Source selection
    preferred_sources: list[str] = field(default_factory=list)

    # Education
    education_level: str = "ANY"

    # Constraints
    visa_sponsorship_needed: bool = False
    company_size_preference: str = "ANY"

    # Role aliases (alternative names for the same role)
    job_title_aliases: list[str] = field(default_factory=list)

    # Scoring threshold
    minimum_match_score: int = 50

    # Scoring weights (0.0-1.0, control importance of each dimension)
    weight_title: float = 0.30
    weight_skills: float = 0.30
    weight_location: float = 0.20
    weight_seniority: float = 0.10
    weight_salary: float = 0.05
    weight_work_type: float = 0.05

    # Metadata
    active: bool = True
    created_at: str = ""
    updated_at: str = ""

    # ── Serialization helpers ──────────────────────────────────────────

    def to_db_row(self) -> dict:
        """Convert to a dict suitable for SQLite INSERT/UPDATE."""
        return {
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "target_roles": json.dumps(self.target_roles),
            "skills": json.dumps(self.skills),
            "experience_level": self.experience_level,
            "experience_years_min": self.experience_years_min,
            "experience_years_max": self.experience_years_max,
            "work_types": json.dumps(self.work_types),
            "remote_preference": self.remote_preference,
            "preferred_locations": json.dumps(self.preferred_locations),
            "min_salary": self.min_salary,
            "salary_currency": self.salary_currency,
            "preferred_industries": json.dumps(self.preferred_industries),
            "include_keywords": json.dumps(self.include_keywords),
            "exclude_keywords": json.dumps(self.exclude_keywords),
            "preferred_sources": json.dumps(self.preferred_sources),
            "education_level": self.education_level,
            "visa_sponsorship_needed": int(self.visa_sponsorship_needed),
            "company_size_preference": self.company_size_preference,
            "job_title_aliases": json.dumps(self.job_title_aliases),
            "minimum_match_score": self.minimum_match_score,
            "weight_title": self.weight_title,
            "weight_skills": self.weight_skills,
            "weight_location": self.weight_location,
            "weight_seniority": self.weight_seniority,
            "weight_salary": self.weight_salary,
            "weight_work_type": self.weight_work_type,
            "notes": self.notes,
            "active": int(self.active),
        }

    @classmethod
    def from_db_row(cls, row: dict) -> "CandidateProfile":
        """Reconstitute from a SQLite row dict."""
        return cls(
            id=row.get("id", 0),
            name=row.get("name", ""),
            email=row.get("email", ""),
            phone=row.get("phone", ""),
            target_roles=_json_list(row.get("target_roles")),
            skills=_json_list(row.get("skills")),
            experience_level=row.get("experience_level", "MID"),
            experience_years_min=row.get("experience_years_min", 0),
            experience_years_max=row.get("experience_years_max", 15),
            work_types=_json_list(row.get("work_types")),
            remote_preference=row.get("remote_preference", "ANY"),
            preferred_locations=_json_list(row.get("preferred_locations")),
            min_salary=row.get("min_salary"),
            salary_currency=row.get("salary_currency", "USD"),
            preferred_industries=_json_list(row.get("preferred_industries")),
            include_keywords=_json_list(row.get("include_keywords")),
            exclude_keywords=_json_list(row.get("exclude_keywords")),
            preferred_sources=_json_list(row.get("preferred_sources")),
            education_level=row.get("education_level", "ANY"),
            visa_sponsorship_needed=bool(row.get("visa_sponsorship_needed", 0)),
            company_size_preference=row.get("company_size_preference", "ANY"),
            job_title_aliases=_json_list(row.get("job_title_aliases")),
            minimum_match_score=row.get("minimum_match_score", 50),
            weight_title=float(row.get("weight_title", 0.30)),
            weight_skills=float(row.get("weight_skills", 0.30)),
            weight_location=float(row.get("weight_location", 0.20)),
            weight_seniority=float(row.get("weight_seniority", 0.10)),
            weight_salary=float(row.get("weight_salary", 0.05)),
            weight_work_type=float(row.get("weight_work_type", 0.05)),
            notes=row.get("notes", ""),
            active=bool(row.get("active", 1)),
            created_at=row.get("created_at", ""),
            updated_at=row.get("updated_at", ""),
        )

    @classmethod
    def from_form(cls, form: dict) -> "CandidateProfile":
        """Build a profile from a Flask request.form dict."""
        # Accept work_types as comma-separated (from SPA) or multi-checkbox (from HTML form)
        work_types = _parse_comma_or_newline(form.get("work_types", ""))
        if not work_types:
            work_types = _parse_multi_checkbox(form, "work_types_")

        # Accept preferred_sources as comma-separated (from SPA) or multi-checkbox
        preferred_sources = _parse_comma_or_newline(form.get("preferred_sources", ""))
        if not preferred_sources:
            preferred_sources = _parse_multi_checkbox(form, "source_")

        return cls(
            id=_int_or(form.get("id"), 0),
            name=form.get("name", "").strip(),
            email=form.get("email", "").strip(),
            phone=form.get("phone", "").strip(),
            target_roles=_parse_comma_or_newline(form.get("target_roles", "")),
            skills=_parse_comma_or_newline(form.get("skills", "")),
            experience_level=form.get("experience_level", "MID").upper(),
            experience_years_min=_int_or(form.get("experience_years_min"), 0),
            experience_years_max=_int_or(form.get("experience_years_max"), 15),
            work_types=work_types,
            remote_preference=form.get("remote_preference", "ANY").upper(),
            preferred_locations=_parse_comma_or_newline(form.get("preferred_locations", "")),
            min_salary=_int_or_none(form.get("min_salary")),
            salary_currency=form.get("salary_currency", "USD").upper(),
            preferred_industries=_parse_comma_or_newline(form.get("preferred_industries", "")),
            include_keywords=_parse_comma_or_newline(form.get("include_keywords", "")),
            exclude_keywords=_parse_comma_or_newline(form.get("exclude_keywords", "")),
            preferred_sources=preferred_sources,
            education_level=form.get("education_level", "ANY").upper(),
            visa_sponsorship_needed=form.get("visa_sponsorship_needed") == "on",
            company_size_preference=form.get("company_size_preference", "ANY").upper(),
            job_title_aliases=_parse_comma_or_newline(form.get("job_title_aliases", "")),
            minimum_match_score=_int_or(form.get("minimum_match_score"), 50),
            weight_title=_float_or(form.get("weight_title"), 0.30),
            weight_skills=_float_or(form.get("weight_skills"), 0.30),
            weight_location=_float_or(form.get("weight_location"), 0.20),
            weight_seniority=_float_or(form.get("weight_seniority"), 0.10),
            weight_salary=_float_or(form.get("weight_salary"), 0.05),
            weight_work_type=_float_or(form.get("weight_work_type"), 0.05),
            notes=form.get("notes", "").strip(),
        )


# ──────────────────────────────────────────────────────────────────────────
# Form parsing helpers
# ──────────────────────────────────────────────────────────────────────────

def _json_list(raw) -> list[str]:
    """Safely parse a JSON text column into a list of strings."""
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        val = json.loads(raw)
        return val if isinstance(val, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _parse_comma_or_newline(text: str) -> list[str]:
    """Split text by comma or newline, strip, drop empties."""
    if not text:
        return []
    parts = re.split(r"[,\n]+", text)
    return [p.strip() for p in parts if p.strip()]


def _parse_multi_checkbox(form: dict, prefix: str) -> list[str]:
    """Extract values from form keys like 'work_types_FULL_TIME=on'."""
    result = []
    for key, val in form.items():
        if key.startswith(prefix) and val:
            result.append(key[len(prefix):])
    return result


def _int_or(val, default: int) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _int_or_none(val) -> int | None:
    if val is None or str(val).strip() == "":
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _float_or(val, default: float) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


# ──────────────────────────────────────────────────────────────────────────
# CRUD
# ──────────────────────────────────────────────────────────────────────────

def get_active_profile(user_id: str | None = None) -> CandidateProfile | None:
    """Return the currently active profile for a user, or None.

    Args:
        user_id: Supabase auth user UUID. If None, returns any active profile
                 (backward-compatible fallback for scripts without auth).
    """
    conn = get_connection()
    if user_id:
        row = conn.execute(
            "SELECT * FROM candidate_profiles WHERE user_id = ? AND active = 1 ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM candidate_profiles WHERE active = 1 ORDER BY id DESC LIMIT 1"
        ).fetchone()
    conn.close()
    return CandidateProfile.from_db_row(dict(row)) if row else None


def get_profile(profile_id: int) -> CandidateProfile | None:
    """Get a profile by id."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM candidate_profiles WHERE id = ?", (profile_id,)
    ).fetchone()
    conn.close()
    return CandidateProfile.from_db_row(dict(row)) if row else None


def get_all_profiles() -> list[CandidateProfile]:
    """Return all profiles, newest first."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM candidate_profiles ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [CandidateProfile.from_db_row(dict(r)) for r in rows]


def save_profile(profile: CandidateProfile, user_id: str | None = None, profile_id: int | None = None) -> int:
    """Insert or update a profile. Returns the profile id.

    Args:
        profile: The CandidateProfile to save.
        user_id: Supabase auth user UUID to associate with this profile.
        profile_id: If provided, update this existing profile instead of creating a new one.
    """
    conn = get_connection()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    row = profile.to_db_row()
    row["updated_at"] = now
    if user_id:
        row["user_id"] = user_id

    # If deactivating, deactivate all other profiles for this user
    if row["active"]:
        if user_id:
            conn.execute(
                "UPDATE candidate_profiles SET active = 0 WHERE active = 1 AND user_id = ?",
                (user_id,),
            )
        else:
            conn.execute("UPDATE candidate_profiles SET active = 0 WHERE active = 1")

    existing = None
    if profile_id:
        existing = conn.execute(
            "SELECT id FROM candidate_profiles WHERE id = ?", (profile_id,)
        ).fetchone()

    if existing:
        columns = ", ".join(f"{k} = ?" for k in row.keys())
        values = list(row.values()) + [existing["id"]]
        conn.execute(
            f"UPDATE candidate_profiles SET {columns} WHERE id = ?", values
        )
        profile_id = existing["id"]
    else:
        row["created_at"] = now
        columns = ", ".join(row.keys())
        placeholders = ", ".join("?" for _ in row)
        result = conn.execute(
            f"INSERT INTO candidate_profiles ({columns}) VALUES ({placeholders}) RETURNING id",
            list(row.values()),
        ).fetchone()
        profile_id = result["id"]

    conn.commit()
    conn.close()

    # Update the profile object's id for callers that use it
    profile.id = profile_id
    return profile_id


def deactivate_profile(profile_id: int) -> None:
    """Deactivate a profile."""
    conn = get_connection()
    conn.execute(
        "UPDATE candidate_profiles SET active = 0, updated_at = ? WHERE id = ?",
        (datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), profile_id),
    )
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────────────────────────────────
# Job scoring / matching engine
# ──────────────────────────────────────────────────────────────────────────

def _tokenize(text: str) -> set[str]:
    """Lower-case word tokens, stripping punctuation."""
    if not text:
        return set()
    return set(re.findall(r"[a-z0-9+#.]+", text.lower()))


def score_job_against_profile(
    job: dict,  # row: {id, title, company, location, description, source, salary_range, posted_at, scraped_at, embedding}
    profile: CandidateProfile,
    profile_embedding: list[float] | None = None,  # pre-computed to avoid recomputation
) -> tuple[float, list[str]]:
    """Score a job (0-100) against a candidate profile.

    Level 1 personalization: Uses semantic embedding similarity (cosine
    distance on paraphrase-MiniLM-L3-v2 vectors) to replace the old string-based
    title/skill/location matching.  Falls back to rule-based matching if
    embeddings are unavailable.

    Scoring dimensions:
      - Semantic similarity:     80% (title + skills + location via embeddings)
      - Seniority level:         10% (regex patterns on title)
      - Work type:                5% (keyword match)
      - Salary:                   5% (parsed currency comparison)
      - Company quality tier:   ±5  (Tier 1/2/WITCH bonus/penalty)
      - Include/exclude keywords: ± keyword hits
      - Source preference:       +3 (if job source matches preferred sources)
      - Freshness decay:      ×0.5-1.0 (age in days)
      - Dismissal penalty:    ×0.5-1.0 (learned from user behavior)

    Returns (score, list_of_match_reasons).
    """
    reasons: list[str] = []
    subscores: dict[str, float] = {}

    title = job.get("title", "")
    company = job.get("company", "")
    location = job.get("location", "")
    description = job.get("description", "")
    source = job.get("source", "")
    salary_range = job.get("salary_range") or ""
    posted_at = job.get("posted_at")
    scraped_at = job.get("scraped_at")
    job_embedding = job.get("embedding")  # list[float] or None

    title_lower = title.lower()
    desc_lower = description.lower() if description else ""
    company_lower = company.lower()
    location_lower = location.lower()

    # ── Determine if we can use semantic embedding matching ──────────────
    use_embeddings = False
    computed_profile_embedding = profile_embedding  # may be None (not provided)

    if job_embedding and isinstance(job_embedding, list) and len(job_embedding) > 0:
        from data_collection.embedding import (
            embed_profile, cosine_similarity, is_embedding_valid,
        )
        # Only use embeddings if the profile has enough information to embed
        has_profile_info = bool(
            (profile.target_roles or profile.job_title_aliases)
            and (profile.skills or profile.preferred_locations)
        )
        if has_profile_info and is_embedding_valid(job_embedding):
            # Use pre-computed profile embedding if provided (for batch scoring),
            # otherwise compute it now
            if computed_profile_embedding is None:
                computed_profile_embedding = embed_profile(
                    target_roles=profile.target_roles + profile.job_title_aliases,
                    skills=profile.skills,
                    preferred_locations=profile.preferred_locations,
                    include_keywords=profile.include_keywords,
                )
            if is_embedding_valid(computed_profile_embedding):
                use_embeddings = True

    # ── 1. Semantic similarity (80% of total when embeddings available) ──
    semantic_max = 80.0
    semantic_score = 0.0

    if use_embeddings and computed_profile_embedding:
        similarity = cosine_similarity(computed_profile_embedding, job_embedding)
        # Map cosine similarity [0,1] to score range [0, 80]
        # Apply a sigmoid-like curve so similarity > 0.5 gets amplified
        if similarity >= 0.8:
            semantic_score = semantic_max * 0.95  # near-perfect match
        elif similarity >= 0.6:
            semantic_score = semantic_max * 0.75 + (similarity - 0.6) * semantic_max * 0.5
        elif similarity >= 0.4:
            semantic_score = semantic_max * 0.4 + (similarity - 0.4) * semantic_max * 1.75
        else:
            semantic_score = similarity * semantic_max  # linear below 0.4

        semantic_score = min(semantic_max, round(semantic_score, 1))
        subscores["semantic"] = semantic_score
        reasons.append(f"Semantic match: {similarity:.0%} similarity "
                       f"(roles={', '.join(profile.target_roles[:3])}, "
                       f"skills={', '.join(profile.skills[:4])})")
    else:
        # ── Fallback: legacy string-based title, skills, location matching ──
        # Title matching
        title_max = 30.0
        title_score = 0.0
        all_targets = profile.target_roles + profile.job_title_aliases
        if all_targets:
            job_canonical = _normalize_title_to_canonical(title)
            for role in all_targets:
                role_lower = role.lower().strip()
                if not role_lower:
                    continue
                if role_lower in title_lower:
                    title_score = title_max
                    reasons.append(f"Title matches target role: {role}")
                    break
                role_canonical = _normalize_title_to_canonical(role)
                overlap = job_canonical & role_canonical
                if overlap:
                    overlap_score = min(title_max, len(overlap) * (title_max / max(len(role_canonical), 1)))
                    if overlap_score > title_score:
                        title_score = overlap_score
                        reasons.append(f"Title canonical match ({', '.join(sorted(overlap))})")
            if title_score == 0:
                target_words = set()
                for role in all_targets:
                    target_words.update(_tokenize(role))
                title_words = _tokenize(title)
                word_overlap = target_words & title_words
                if word_overlap:
                    title_score = min(20, len(word_overlap) * 3)
                    reasons.append(f"Partial title match: {', '.join(sorted(word_overlap))}")
        subscores["title"] = title_score

        # Skill matching
        skill_max = 30.0
        skill_score = 0.0
        if profile.skills:
            matched_skills: list[str] = []
            for skill in profile.skills:
                skill_lower = skill.lower().strip()
                if not skill_lower:
                    continue
                skill_forms = {skill_lower}
                if skill_lower in _SKILL_TAXONOMY:
                    skill_forms.update(s.lower() for s in _SKILL_TAXONOMY[skill_lower])
                for skill_form in skill_forms:
                    if re.search(rf"\b{re.escape(skill_form)}\b", desc_lower):
                        matched_skills.append(skill)
                        break
                    elif skill_form in desc_lower:
                        matched_skills.append(skill)
                        break
                    elif skill_form in title_lower:
                        matched_skills.append(skill)
                        break
            if matched_skills:
                skill_pct = len(set(matched_skills)) / len(profile.skills)
                skill_score = min(skill_max, round(skill_pct * skill_max, 1))
                reasons.append(
                    f"Skills matched ({len(set(matched_skills))}/{len(profile.skills)}): "
                    f"{', '.join(matched_skills[:6])}"
                )
        subscores["skills"] = skill_score

        # Location matching
        loc_max = 20.0
        loc_score = 0.0
        if profile.preferred_locations:
            for pref_loc in profile.preferred_locations:
                pref_lower = pref_loc.lower().strip()
                if not pref_lower:
                    continue
                aliases = {pref_lower}
                for metro, metro_aliases in _METRO_AREAS.items():
                    if pref_lower == metro or pref_lower in metro_aliases:
                        aliases.add(metro)
                        aliases.update(a.lower() for a in metro_aliases)
                        break
                for alias in aliases:
                    if alias in location_lower:
                        loc_score = loc_max
                        reasons.append(f"Location matches: {pref_loc}")
                        break
                if loc_score > 0:
                    break
            else:
                loc_words = _tokenize(location)
                for pref_loc in profile.preferred_locations:
                    if _tokenize(pref_loc) & loc_words:
                        loc_score = 10
                        reasons.append(f"Partial location match: {pref_loc}")
                        break
        elif profile.remote_preference == "REMOTE":
            remote_aliases = _METRO_AREAS.get("remote", [])
            if any(w in location_lower for w in remote_aliases):
                loc_score = 15
                reasons.append("Remote location")
        subscores["location"] = loc_score
        subscores["semantic"] = 0.0  # placeholder

    # ── 2. Seniority level (10% of total) ──
    seniority_max = 10.0
    seniority_score = 0.0

    if profile.experience_level == "MID":
        mid_explicit = re.search(r"\b(mid.level|mid|intermediate)\b", title_lower)
        if mid_explicit:
            seniority_score = seniority_max
            reasons.append(f"Seniority level: {profile.experience_level}")
        else:
            has_generic = re.search(r"\b(engineer|developer)\b", title_lower)
            has_conflict = re.search(
                r"\b(junior|jr\.?|senior|sr\.?|staff|principal|lead|head|director|vp|architect)\b",
                title_lower,
            )
            if has_generic and not has_conflict:
                seniority_score = seniority_max * 0.7
                reasons.append(f"Seniority level: {profile.experience_level} (generic)")
    else:
        exp_keywords = _SENIORITY_PATTERNS.get(profile.experience_level, [])
        for pattern in exp_keywords:
            if re.search(pattern, title_lower):
                seniority_score = seniority_max
                reasons.append(f"Seniority level: {profile.experience_level}")
                break

    # Experience years match (bonus, shares seniority weight)
    exp_years = _parse_experience_years(description)
    if exp_years and profile.experience_years_min > 0:
        req_min, req_max = exp_years
        if profile.experience_years_min >= req_min and profile.experience_years_min <= req_max:
            seniority_score += 3
            reasons.append(f"Experience match: {req_min}-{req_max}y required, you have {profile.experience_years_min}y")
        elif abs(profile.experience_years_min - req_min) <= 2:
            seniority_score += 1.5
            reasons.append(f"Close experience match: {req_min}-{req_max}y required")

    subscores["seniority"] = min(seniority_max + 3, seniority_score)

    # ── 3. Work type (5% of total) ──
    work_max = 5.0
    work_score = 0.0

    if profile.work_types:
        combined = f"{title_lower} {desc_lower}"
        for wt in profile.work_types:
            if wt.lower() in combined:
                work_score = work_max
                reasons.append(f"Work type: {wt}")
                break

    subscores["work_type"] = work_score

    # ── 4. Salary (5% of total) ──
    salary_max = 5.0
    salary_score = 0.0

    if profile.min_salary and salary_range:
        parsed_salary = _parse_salary_usd(salary_range, profile.salary_currency)
        if parsed_salary and parsed_salary >= profile.min_salary:
            salary_score = salary_max
            reasons.append(f"Salary meets minimum (${parsed_salary:,} ≥ ${profile.min_salary:,})")
        elif parsed_salary:
            salary_score = salary_max * 0.5
            reasons.append("Salary listed but below minimum")
        else:
            salary_score = salary_max * 0.5
            reasons.append("Salary listed (could not parse amount)")
    elif profile.min_salary and not salary_range:
        salary_score = 0

    subscores["salary"] = salary_score

    # ── 5. Company quality tier ──
    company_bonus = 0.0
    company_check = company_lower.strip()
    if company_check in _COMPANY_TIER_1:
        company_bonus = 5
        reasons.append(f"Tier 1 company: {company}")
    elif company_check in _COMPANY_TIER_2:
        company_bonus = 3
        reasons.append(f"Tier 2 company: {company}")
    elif company_check in _COMPANY_TIER_PENALTY:
        company_bonus = -5
        reasons.append(f"WITCH/body shop company: {company}")

    # ── 6. Keyword bonus / penalty ──
    combined_text = f"{title_lower} {company_lower} {desc_lower}"

    keyword_bonus = 0.0
    if profile.include_keywords:
        inc_hits = sum(1 for kw in profile.include_keywords if kw.lower() in combined_text)
        if inc_hits:
            keyword_bonus = min(10, inc_hits * 3)
            reasons.append(f"Include keywords: {inc_hits} hits")

    keyword_penalty = 0.0
    if profile.exclude_keywords:
        exclude_hits = sum(1 for kw in profile.exclude_keywords if kw.lower() in combined_text)
        if exclude_hits:
            keyword_penalty = min(25, exclude_hits * 8)
            reasons.append(f"Exclude keyword hit ({exclude_hits}): -{keyword_penalty}")

    # ── 7. Source preference ──
    source_bonus = 0.0
    if profile.preferred_sources and source in profile.preferred_sources:
        source_bonus = 3
        reasons.append(f"Preferred source: {source}")

    # ── Compile weighted score ──
    if use_embeddings:
        # New scoring: semantic embedding (80%) + rule-based dimensions (20%)
        raw_score = (
            subscores["semantic"]
            + subscores["seniority"] * profile.weight_seniority / 0.10
            + subscores["work_type"] * profile.weight_work_type / 0.05
            + subscores["salary"] * profile.weight_salary / 0.05
            + company_bonus
            + keyword_bonus
            + source_bonus
            - keyword_penalty
        )
    else:
        # Legacy scoring: title (30%) + skills (30%) + location (20%) + ...
        raw_score = (
            subscores["title"] * profile.weight_title / 0.30
            + subscores["skills"] * profile.weight_skills / 0.30
            + subscores["location"] * profile.weight_location / 0.20
            + subscores["seniority"] * profile.weight_seniority / 0.10
            + subscores["work_type"] * profile.weight_work_type / 0.05
            + subscores["salary"] * profile.weight_salary / 0.05
            + company_bonus
            + keyword_bonus
            + source_bonus
            - keyword_penalty
        )

    # ── 8. Freshness decay ──
    decay = _compute_freshness_decay(posted_at, scraped_at)
    if decay < 1.0:
        reasons.append(f"Age decay: ×{decay:.2f}")
    raw_score *= decay

    # ── 9. Dismissal penalty ──
    if profile.id:
        matched_skill_set = set(s.lower() for s in (profile.skills or []))
        dismissal_penalty = _get_dismissed_skill_penalty(profile.id, matched_skill_set)
        if dismissal_penalty < 1.0:
            reasons.append(f"Dismissal penalty: ×{dismissal_penalty:.2f}")
            raw_score *= dismissal_penalty

    # Clamp to 0-100
    score = max(0.0, min(100.0, round(raw_score, 1)))
    return score, reasons


def score_and_store_matches(
    job_ids: Sequence[int],
    profile: CandidateProfile,
) -> int:
    """Score every given job against the profile and store matches.

    Returns number of matches with score >= profile.minimum_match_score.
    """
    conn = get_connection()
    placeholders = ",".join("?" for _ in job_ids)
    rows = conn.execute(
        f"""SELECT id, title, company, location, description, source, salary_range,
                  posted_at, scraped_at, embedding
            FROM jobs WHERE id IN ({placeholders})""",
        list(job_ids),
    ).fetchall()

    # Pre-compute profile embedding once for all jobs in this batch
    from data_collection.embedding import embed_profile, is_embedding_valid
    profile_emb = None
    try:
        if profile.target_roles or profile.job_title_aliases:
            profile_emb = embed_profile(
                target_roles=profile.target_roles + profile.job_title_aliases,
                skills=profile.skills,
                preferred_locations=profile.preferred_locations,
                include_keywords=profile.include_keywords,
            )
            if not is_embedding_valid(profile_emb):
                profile_emb = None
    except Exception:
        profile_emb = None

    good = 0
    for row in rows:
        job_dict = dict(row)
        score, reasons = score_job_against_profile(job_dict, profile, profile_embedding=profile_emb)

        conn.execute(
            """INSERT INTO profile_job_matches
               (profile_id, job_id, score, match_reasons)
               VALUES (?, ?, ?, ?)
               ON CONFLICT (profile_id, job_id) DO UPDATE SET
                   score = EXCLUDED.score,
                   match_reasons = EXCLUDED.match_reasons""",
            (profile.id or 1,
             row["id"], score, json.dumps(reasons)),
        )
        if score >= profile.minimum_match_score:
            good += 1

    conn.commit()
    conn.close()
    logger.info(
        "Scored %d jobs against profile: %d above threshold (≥%d)",
        len(rows), good, profile.minimum_match_score,
    )
    return good


def score_all_new_jobs(profile: CandidateProfile | None = None, user_id: str | None = None) -> int:
    """Score all jobs not yet matched against the active profile."""
    if profile is None:
        profile = get_active_profile(user_id=user_id)
    if profile is None:
        logger.warning("No active profile found — skipping scoring")
        return 0

    conn = get_connection()
    # Get profile ID
    if user_id:
        row = conn.execute(
            "SELECT id FROM candidate_profiles WHERE user_id = ? AND active = 1 ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT id FROM candidate_profiles WHERE active = 1 ORDER BY id DESC LIMIT 1"
        ).fetchone()

    if not row:
        conn.close()
        return 0

    profile_id = row["id"]
    profile.id = profile_id

    # Find unscored jobs belonging to this user (multi-tenant isolation).
    # Only score jobs collected by this user — don't leak other users' jobs.
    profile_user_id = None
    if user_id:
        profile_user_id = user_id
    elif profile.id:
        # Fallback: look up the user_id from the profile record
        conn2 = get_connection()
        p_row = conn2.execute(
            "SELECT user_id FROM candidate_profiles WHERE id = ?", (profile.id,)
        ).fetchone()
        conn2.close()
        if p_row and p_row.get("user_id"):
            profile_user_id = p_row["user_id"]

    if profile_user_id:
        rows = conn.execute(
            """SELECT j.id FROM jobs j
               LEFT JOIN profile_job_matches pjm
                 ON j.id = pjm.job_id AND pjm.profile_id = ?
               WHERE pjm.job_id IS NULL AND j.user_id = ?
               ORDER BY j.scraped_at DESC""",
            (profile_id, profile_user_id),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT j.id FROM jobs j
               LEFT JOIN profile_job_matches pjm
                 ON j.id = pjm.job_id AND pjm.profile_id = ?
               WHERE pjm.job_id IS NULL
               ORDER BY j.scraped_at DESC""",
            (profile_id,),
        ).fetchall()
    conn.close()

    if not rows:
        logger.info("All jobs already scored against profile %d", profile_id)
        return 0

    job_ids = [r["id"] for r in rows]
    logger.info("Scoring %d new jobs against profile...", len(job_ids))
    return score_and_store_matches(job_ids, profile)


# ──────────────────────────────────────────────────────────────────────────
# Filter-aware collection helpers
# ──────────────────────────────────────────────────────────────────────────

def get_enabled_sources(user_id: str | None = None) -> list[str]:
    """Return which job sources should run based on profile preferences.

    If profile has preferred_sources, return those. Otherwise return all.
    """
    profile = get_active_profile(user_id=user_id)
    if profile and profile.preferred_sources:
        return [s for s in profile.preferred_sources if s in ALL_SOURCES]
    return ALL_SOURCES


def get_search_keywords(user_id: str | None = None) -> list[str]:
    """Return search keywords derived from the profile for API-based collectors."""
    profile = get_active_profile(user_id=user_id)
    if not profile:
        return []

    keywords = list(profile.target_roles)
    keywords.extend(profile.job_title_aliases)
    keywords.extend(profile.include_keywords)
    # Deduplicate and prioritize
    seen = set()
    result = []
    for kw in keywords:
        if kw.lower() not in seen:
            seen.add(kw.lower())
            result.append(kw)
    return result


def get_location_filters(user_id: str | None = None) -> list[str]:
    """Return search locations derived from the profile."""
    profile = get_active_profile(user_id=user_id)
    if not profile:
        return []
    return profile.preferred_locations


# ──────────────────────────────────────────────────────────────────────────
# User feedback — dismiss / save jobs for behavioral learning
# ──────────────────────────────────────────────────────────────────────────


def dismiss_job(profile_id: int, job_id: int) -> bool:
    """Mark a job as dismissed so future similar jobs get penalized.

    Returns True if the row was updated, False if not found.
    """
    conn = get_connection()
    conn.execute(
        """INSERT INTO profile_job_matches
           (profile_id, job_id, score, match_reasons, dismissed)
           VALUES (?, ?, 0, '[]', 1)
           ON CONFLICT (profile_id, job_id) DO UPDATE SET
               dismissed = 1""",
        (profile_id, job_id),
    )
    conn.commit()
    conn.close()
    return True


def save_job(profile_id: int, job_id: int) -> bool:
    """Mark a job as saved (clears dismissed flag, positive signal).

    Returns True if the row was updated.
    """
    conn = get_connection()
    conn.execute(
        """INSERT INTO profile_job_matches
           (profile_id, job_id, score, match_reasons, dismissed)
           VALUES (?, ?, 0, '[]', 0)
           ON CONFLICT (profile_id, job_id) DO UPDATE SET
               dismissed = 0""",
        (profile_id, job_id),
    )
    conn.commit()
    conn.close()
    return True
