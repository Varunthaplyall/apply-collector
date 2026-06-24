# Personalization Architecture Plan

> Senior Architect Recommendation — June 2026

## Current State

The system uses a **weighted rule-based heuristic scorer** in `data_collection/user_profile.py`
(`score_job_against_profile`) with these dimensions:

| Dimension    | Method                                            | Weight |
| ------------ | ------------------------------------------------- | ------ |
| Title match  | Canonical term synonym map + word overlap         | 30%    |
| Skills       | Taxonomy expansion → substring regex in desc      | 30%    |
| Location     | Metro area alias expansion                        | 20%    |
| Seniority    | Regex patterns on title                           | 10%    |
| Work type    | Keyword in title+description                      | 5%     |
| Salary       | Parsed USD-equivalent midpoint comparison         | 5%     |
| Bonuses      | Company tier (+5/+3/-5), keywords (±), source (+3) | additive |
| Decay        | `_compute_freshness_decay` (0.5-1.0× multiplier)  | multiplicative |
| Dismissal    | Skill overlap with dismissed jobs                 | multiplicative |

**Core limitation:** This is fundamentally string-matching against a static profile. It has no
semantic modeling, no behavioral learning, and no collaborative signal. "Senior Frontend
Engineer" and "Lead React Developer" are effectively the same role but score differently.

---

## Seven-Level Personalization Roadmap

### Level 1 (IMPLEMENTED) — Embedding-Based Semantic Matching
**Highest ROI — ~3 days — DONE**

Replace hardcoded synonym/taxonomy maps with vector embeddings.

- Model: `paraphrase-MiniLM-L3-v2` (384-dim, 17MB, fits Render free tier 512MB RAM)
- Storage: PostgreSQL `double precision[]` column on `jobs`
- Scoring: `cosine_similarity(job_embedding, profile_embedding)` replaces title+skill+location string matching
- Rule-based bonuses (company tier, salary, etc.) layer on top

**Impact:** "React Native Developer" matches "Mobile Engineer (React Native)" without any
manual taxonomy. Works across languages. No maintenance burden.

**Files:**
- `data_collection/embedding.py` — embedding model, `embed_text()`, `compute_similarity()`
- `data_collection/database.py` — `embedding` column on `jobs` table
- `data_collection/user_profile.py` — modified `score_job_against_profile()` to use vector similarity
- `scripts/backfill_embeddings.py` — one-time backfill for existing jobs

---

### Level 2 — Behavioral Implicit Feedback (~1 week)

Learn from what the user actually clicks, not just what they said.

**Signals to capture:**
```
viewed + no action  → weak negative (score -= 2)
viewed + clicked    → weak positive  (score += 3)
viewed + saved      → strong positive (score += 8)
viewed + dismissed  → strong negative (score -= 10)
viewed + applied    → very strong positive (score += 15)
time_spent_on_card  → continuous signal (longer = more interest)
```

**Architecture:**
```
┌────────────────────┐     ┌───────────────────┐     ┌──────────────────┐
│ React Frontend     │────▶│ /api/interactions  │────▶│ user_interactions│
│ IntersectionObs.   │     │ POST endpoint      │     │ table            │
└────────────────────┘     └───────────────────┘     └──────────────────┘
                                                              │
┌────────────────────┐     ┌───────────────────┐              │
│ Re-rank engine     │◀────│ interaction_score │◀─────────────┘
│ final = α·profile  │     │ (weighted sum of  │
│  + β·implicit      │     │  recent similar)  │
│  + γ·freshness     │     │                   │
└────────────────────┘     └───────────────────┘
```

**Schema addition:**
```sql
CREATE TABLE user_interactions (
  user_id UUID, job_id INT, interaction_type TEXT,
  dwell_ms INT, created_at TIMESTAMPTZ,
  PRIMARY KEY (user_id, job_id, interaction_type)
);
```

---

### Level 3 — LLM-Powered Daily Digest (~1 week)

Instead of a list — a personalized daily summary.

**Example output:**
> **Your Daily Match — June 24, 2026**
>
> 🔥 **Top Pick:** Senior Backend Engineer at Stripe (94% match)
> *This role maps perfectly to your Python/Django stack. Tier 1 company, $180k+.*
>
> ⭐ **Strong Matches (3):** ...
> 🆕 **New this week (12):** ...
> 💡 **Tip:** 23 new Python jobs in Bengaluru this week (↑15%)

**Cost:** ~$0.002/digest (GPT-4o-mini). $2/day for 1000 users.

**Endpoint:** `POST /api/digest` — generates and caches in `generated_digests` table.

---

### Level 4 — Two-Tower Neural Recommender (~2-3 weeks)

Production-grade model used by LinkedIn, Indeed, etc.

```
         ┌─────────────────────┐
Job ────▶│ Job Tower (FFN)     │──┐
         └─────────────────────┘  │    ┌──────────┐
                                  ├───▶│ Dot      │──▶ P(relevant)
         ┌─────────────────────┐  │    │ Product  │
User ───▶│ User Tower (FFN)    │──┘    └──────────┘
         └─────────────────────┘
```

- Train nightly on `(user, job) → {clicked, saved, dismissed, applied}` data
- Export to ONNX for fast inference
- Requires sufficient interaction volume (>1000 interactions)

**Tech stack:** PyTorch, ONNX Runtime, nightly cron job.

---

### Level 5 — Exploration/Exploitation Slots (~1 week)

Break the filter bubble — show diverse jobs alongside best matches.

```
Top 50 jobs to display:
  - 80% slots: highest scoring ("exploit")
  - 10% slots: diverse-by-embedding ("explore similar")
  - 10% slots: random high-quality Tier 1/2 ("serendipity")
```

Also compute a **job similarity graph**: when user saves job X, boost jobs with similar embeddings.

---

### Level 6 — Real-Time Feature Store (~3-4 weeks)

Pre-compute per-user features hourly for <50ms inference.

```
user_123_features = {
    "embedding": [...],           # aggregated profile + behavior
    "clicked_skills": {...},      # TF-IDF of clicked job skills
    "avg_salary_clicked": 145000,
    "preferred_company_tiers": {"T1": 0.7, "T2": 0.3},
    "active_hours": [9,10,11,14,15],
    "search_velocity": 0.8,
    "preference_shift_vector": [...],
}
```

**For when you have >1000 active users.**

---

### Level 7 — LLM Agent for Full Personalization (~4-6 weeks)

An LLM agent that understands career trajectory and recommends accordingly.

```
System: You are a career coach with access to:
  - User's full profile, skill history, interaction data
  - 20,000+ job listings with embeddings and metadata
  - Tools: search_jobs, compare_companies, estimate_salary_growth,
           check_culture_fit, suggest_skill_gaps

User: "I'm a mid-level backend engineer bored of fintech,
       want to move into AI/ML but don't have ML experience."

Agent: → Finds bridge roles at companies with internal mobility
       → Suggests skill gaps and learning resources
       → Recommends 3 high-probability transitions
```

---

## Implementation Order (Recommended)

1. ✅ **Level 1** — Embedding semantic matching (this PR)
2. **Level 2** — Behavioral implicit feedback (next)
3. **Level 3** — LLM daily digest (user delight, immediate value)
4. **Level 5** — Exploration/exploitation (simple, high impact)
5. **Level 4** — Two-tower recommender (when interaction data is sufficient)
6. **Level 6** — Feature store (when scaling past 1K users)
7. **Level 7** — LLM agent (moonshot, long-term)

---

## Key Design Principles

1. **Composable scores** — Every level adds a layer; no layer breaks the previous one.
   `final_score = semantic_similarity + behavioral_boost + freshness_decay + exploration_noise`

2. **No Selenium/Playwright for scoring** — All personalization runs on server-side data.

3. **No hardcoded taxonomy maps** — Embeddings eliminate the maintenance burden.

4. **User feedback loop** — Every dismiss/save is training data for the next level.

5. **Cost-conscious** — Local models for embeddings (free), cheap LLM calls for digests ($0.002/digest).

6. **Graceful degradation** — If embedding model fails, fall back to rule-based scoring.
