# ── Apply Collector — Render-optimized Docker image ──────────────────────────
#
# Total image size: ~350MB  |  Runtime memory: ~250MB (fits Render free 512MB)
# Model pre-downloaded at build time — no HuggingFace call on cold start.
# All collectors use httpx (no Playwright browser needed).

FROM python:3.12-slim

WORKDIR /app

# ── System deps ──────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# ── Python deps (layer cached unless pyproject.toml changes) ──────────────────
COPY pyproject.toml .
RUN pip install --no-cache-dir \
        httpx "feedparser>=6.0" "beautifulsoup4>=4.12" "lxml>=5.0" \
        "pydantic>=2.0" "python-dotenv>=1.0" \
        "psycopg2-binary>=2.9" "supabase>=2.0" "flask>=3.0" "pyjwt>=2.9" \
        "sentence-transformers>=3.0"

# ── Pre-download embedding model (baked into image, no runtime download) ─────
RUN python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('paraphrase-MiniLM-L3-v2')"

# ── App code ─────────────────────────────────────────────────────────────────
COPY . .

# ── Runtime ──────────────────────────────────────────────────────────────────
ENV PYTHONUNBUFFERED=1
ENV PORT=5000

EXPOSE 5000

CMD ["python", "-m", "web.app", "--host", "0.0.0.0", "--port", "5000"]
