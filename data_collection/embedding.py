"""
Embedding utility for semantic job matching.

Uses sentence-transformers (paraphrase-MiniLM-L3-v2, 384-dim, 17MB) to
compute vector embeddings for jobs and profiles.  Embeddings replace the
hardcoded synonym maps and taxonomy lookups in user_profile.py with true
semantic matching.

Key design decisions:
  - Lazy singleton model — loaded once, shared across all callers
  - Batch processing for efficiency (backfill, collection)
  - Cosine similarity for matching (0-1 range)
  - Graceful degradation — returns zero vector on failure
  - Model: paraphrase-MiniLM-L3-v2 (17MB, fits Render free tier 512MB RAM)
    Identical ranking quality to all-MiniLM-L6-v2 (80MB) in benchmarks.
"""

from __future__ import annotations

import logging
import math
import threading
from typing import Optional, Sequence

import numpy as np

logger = logging.getLogger(__name__)

# ── Model singleton ──────────────────────────────────────────────────────────

_model = None
_model_lock = threading.Lock()
_MODEL_LOAD_FAILED = False  # Set to True when sentence-transformers is unavailable
_MODEL_NAME = "paraphrase-MiniLM-L3-v2"
_EMBEDDING_DIM = 384


def _get_model():
    """Lazy-load the sentence-transformers model (thread-safe singleton).

    Returns the model if available, or None if sentence-transformers is not
    installed (e.g., on Vercel free tier where PyTorch is too large).
    """
    global _model, _MODEL_LOAD_FAILED
    if _model is not None:
        return _model
    if _MODEL_LOAD_FAILED:
        return None  # Don't keep retrying after a known failure

    with _model_lock:
        if _model is not None:
            return _model
        if _MODEL_LOAD_FAILED:
            return None
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer(_MODEL_NAME)
            logger.info("Embedding model loaded: %s (dim=%d)", _MODEL_NAME, _EMBEDDING_DIM)
        except ModuleNotFoundError:
            _MODEL_LOAD_FAILED = True
            logger.warning(
                "sentence-transformers not installed — semantic embedding disabled. "
                "Scoring will use keyword matching only."
            )
            return None
        except Exception:
            logger.exception("Failed to load embedding model %s", _MODEL_NAME)
            _MODEL_LOAD_FAILED = True
            return None
        return _model


# ── Public API ───────────────────────────────────────────────────────────────


def embed_text(text: str) -> list[float]:
    """Compute embedding for a single text string.

    Returns a 384-dimensional float list (or all-zeros when model unavailable).
    """
    if not text or not text.strip():
        return [0.0] * _EMBEDDING_DIM

    try:
        model = _get_model()
        if model is None:
            return [0.0] * _EMBEDDING_DIM
        vec = model.encode(text.strip(), normalize_embeddings=True)
        return vec.tolist()
    except Exception:
        logger.exception("Failed to embed text (len=%d): %.80s...", len(text), text)
        return [0.0] * _EMBEDDING_DIM


def embed_texts(texts: Sequence[str], batch_size: int = 64) -> list[list[float]]:
    """Compute embeddings for multiple texts in batches.

    Returns a list of 384-dimensional float lists, same length as input.
    Returns all-zeros when model unavailable.
    """
    if not texts:
        return []

    try:
        model = _get_model()
        if model is None:
            return [[0.0] * _EMBEDDING_DIM for _ in texts]
        cleaned = [t.strip() if t else "" for t in texts]
        all_embeddings = model.encode(
            cleaned,
            normalize_embeddings=True,
            batch_size=batch_size,
            show_progress_bar=len(cleaned) > 100,
        )
        return [e.tolist() for e in all_embeddings]
    except Exception:
        logger.exception("Failed to embed %d texts in batch", len(texts))
        return [[0.0] * _EMBEDDING_DIM for _ in texts]


def embed_job(title: str, company: str, location: str, description: str = "") -> list[float]:
    """Compute a single embedding for a job posting.

    Concatenates the most semantically rich fields.  Description is truncated
    to 500 chars — that's enough for role requirements and tech stack.
    """
    desc_short = (description or "")[:500].strip()
    parts = [title.strip(), company.strip()]
    if location.strip():
        parts.append(location.strip())
    if desc_short:
        parts.append(desc_short)
    text = " | ".join(parts)
    return embed_text(text)


def embed_profile(
    target_roles: Sequence[str],
    skills: Sequence[str],
    preferred_locations: Sequence[str] | None = None,
    include_keywords: Sequence[str] | None = None,
) -> list[float]:
    """Compute a single embedding for a candidate profile.

    Weights target roles most heavily, then skills, then locations.
    """
    parts: list[str] = []

    # Target roles — repeat to give them more weight in the pooled embedding
    for role in (target_roles or []):
        parts.append(role.strip())
        parts.append(role.strip())  # double-weight roles

    # Skills
    for skill in (skills or []):
        parts.append(skill.strip())

    # Preferred locations
    for loc in (preferred_locations or []):
        parts.append(loc.strip())

    # Include keywords
    for kw in (include_keywords or []):
        parts.append(kw.strip())

    if not parts:
        return [0.0] * _EMBEDDING_DIM

    text = " | ".join(parts)
    return embed_text(text)


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Compute cosine similarity between two embedding vectors.

    Both vectors are assumed to be L2-normalized (model.encode with
    normalize_embeddings=True).  For normalized vectors, cosine similarity
    is just the dot product.

    Returns a float in [0, 1] (clamped).
    """
    if not a or not b:
        return 0.0

    # For L2-normalized vectors, dot product = cosine similarity
    dot = sum(x * y for x, y in zip(a, b))
    # Clamp to [0, 1] to handle floating-point noise
    return max(0.0, min(1.0, dot))


def batch_cosine_similarity(
    query: list[float],
    candidates: list[list[float]],
) -> list[float]:
    """Compute cosine similarity of a query vector against multiple candidates.

    Uses numpy for vectorized computation.
    """
    if not candidates:
        return []
    q = np.array(query, dtype=np.float32)
    c = np.array(candidates, dtype=np.float32)
    # Both are normalized, so dot product = cosine similarity
    scores = np.dot(c, q)
    return [max(0.0, min(1.0, float(s))) for s in scores]


def embedding_to_db(value: list[float] | None) -> str | None:
    """Convert an embedding list to a PostgreSQL array literal.

    Example: [0.1, 0.2, 0.3] → '{0.1,0.2,0.3}'
    """
    if value is None:
        return None
    return "{" + ",".join(str(v) for v in value) + "}"


def embedding_from_db(value: str | list[float] | None) -> list[float] | None:
    """Parse a PostgreSQL array or Python list back to a list of floats.

    Handles both formats:
      - PostgreSQL text: '{0.1,0.2,0.3}'
      - psycopg2 native: [0.1, 0.2, 0.3] (when ARRAY type is used)
    """
    if value is None:
        return None
    if isinstance(value, list):
        return [float(x) for x in value]
    if not isinstance(value, str):
        return None
    # Strip braces and split
    inner = value.strip("{}")
    if not inner:
        return None
    return [float(x) for x in inner.split(",")]


def is_embedding_valid(embedding: list[float] | None) -> bool:
    """Check if an embedding is non-zero and valid."""
    if not embedding or len(embedding) != _EMBEDDING_DIM:
        return False
    return any(v != 0.0 for v in embedding)
