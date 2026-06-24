# ── Apply Collector — Render-optimized Docker image ──────────────────────────
#
# Multi-stage build: Stage 1 builds the React SPA, Stage 2 runs Flask + Python.
# Total image size: ~400MB  |  Runtime memory: ~300MB (fits Render free 512MB)
# Model pre-downloaded at build time — no HuggingFace call on cold start.
# All collectors use httpx (no Playwright browser needed).

# ═══════════════════════════════════════════════════════════════════════════════
# Stage 1 — Build React SPA
# ═══════════════════════════════════════════════════════════════════════════════
FROM node:20-alpine AS frontend

# Vite build-time env vars (VITE_ prefix is required for import.meta.env exposure)
# These are Supabase publishable keys — safe to include in the image.
ARG VITE_SUPABASE_URL=https://gmqoclqbglkhjpwwfntc.supabase.co
ARG VITE_SUPABASE_ANON_KEY=sb_publishable_vN59M8NXySGlacCch4oc2g_SDIuwMG0
ENV VITE_SUPABASE_URL=$VITE_SUPABASE_URL
ENV VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY

WORKDIR /app/web/dashboard

COPY web/dashboard/package.json web/dashboard/package-lock.json ./
RUN npm ci

COPY web/dashboard/ ./
RUN npm run build

# ═══════════════════════════════════════════════════════════════════════════════
# Stage 2 — Python runtime
# ═══════════════════════════════════════════════════════════════════════════════
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

# ── Copy built React SPA from frontend stage ─────────────────────────────────
COPY --from=frontend /app/web/static/dist /app/web/static/dist

# ── Runtime ──────────────────────────────────────────────────────────────────
ENV PYTHONUNBUFFERED=1
ENV PORT=5000

EXPOSE 5000

CMD ["python", "-m", "web.app", "--host", "0.0.0.0", "--port", "5000"]
