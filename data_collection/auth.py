"""
Supabase JWT authentication for Flask.

Provides:
  - require_auth decorator — protect API routes with Bearer token validation
  - get_current_user() — retrieve the authenticated user_id from Flask's g
  - Auth helpers for token validation using PyJWT + JWKS

Architecture:
  The React frontend authenticates via Supabase JS client and stores the session
  (access_token, refresh_token) in localStorage.  For every API call, the
  frontend sends the access_token as an ``Authorization: Bearer <token>`` header.

  Supabase access tokens are signed with ES256 (ECDSA).  We validate them
  by fetching the JWKS (public keys) from Supabase's well-known endpoint.
  Keys are cached and automatically refreshed on key mismatch.
"""

from __future__ import annotations

import logging
from functools import wraps
from typing import Optional

from flask import g, jsonify, request

from data_collection.config import SUPABASE_URL

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JWT validation via JWKS
# ---------------------------------------------------------------------------

try:
    import jwt as pyjwt
    from jwt import PyJWKClient, PyJWKClientError
    _HAS_JWT = True
except ImportError:
    _HAS_JWT = False
    pyjwt = None  # type: ignore[assignment]
    PyJWKClient = None  # type: ignore[assignment]
    PyJWKClientError = Exception  # type: ignore[assignment]

if not _HAS_JWT:
    import warnings
    warnings.warn(
        "PyJWT is not installed. Auth token validation will fail. "
        "Install it with: pip install pyjwt[crypto]",
        RuntimeWarning,
        stacklevel=1,
    )

_jwks_client: Optional["PyJWKClient"] = None  # type: ignore[valid-type]


def _get_jwks_client() -> Optional["PyJWKClient"]:  # type: ignore[valid-type]
    """Create or return the cached JWKS client for this Supabase project."""
    global _jwks_client
    if _jwks_client is not None:
        return _jwks_client

    if not SUPABASE_URL:
        logger.error("SUPABASE_URL is not set — cannot fetch JWKS")
        return None

    jwks_url = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
    try:
        _jwks_client = PyJWKClient(jwks_url, cache_keys=True, lifespan=3600)
        logger.info("JWKS client initialized: %s", jwks_url)
    except Exception as exc:
        logger.error("Failed to create JWKS client: %s", exc)
        return None

    return _jwks_client


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate a Supabase-issued JWT (ES256 via JWKS).

    Returns the token payload (dict with ``sub``, ``email``, etc.) or
    ``None`` if the token is invalid / expired.
    """
    if not _HAS_JWT:
        logger.error("PyJWT is not installed — cannot validate tokens")
        return None

    client = _get_jwks_client()
    if not client:
        logger.error("JWKS client not available — cannot validate tokens")
        return None

    try:
        # Get the signing key from JWKS (matches kid in token header to JWKS key)
        signing_key = client.get_signing_key_from_jwt(token)
        # Validate audience: should match the Supabase project reference.
        # Supabase JWTs include `aud: "authenticated"` as the default audience.
        # We verify this to reject tokens from other Supabase projects.
        payload = pyjwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            audience="authenticated",
            options={
                "require": ["exp", "sub"],
            },
        )
        return payload
    except pyjwt.ExpiredSignatureError:
        logger.warning("JWT decode failed: Token expired")
        return None
    except pyjwt.InvalidSignatureError:
        logger.warning("JWT decode failed: Invalid signature")
        return None
    except PyJWKClientError as exc:
        logger.warning("JWT decode failed (JWKS error): %s", exc)
        # Force refresh JWKS cache on next attempt
        global _jwks_client
        _jwks_client = None
        return None
    except pyjwt.InvalidTokenError as exc:
        logger.warning("JWT decode failed: %s", exc)
        return None


def _extract_token() -> Optional[str]:
    """Pull the Bearer token from the Authorization header."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    return auth_header[len("Bearer "):].strip()


# ---------------------------------------------------------------------------
# Flask helpers
# ---------------------------------------------------------------------------


def get_current_user() -> Optional[str]:
    """Return the authenticated user's Supabase UUID, or None.

    Call this *inside* a route protected by ``@require_auth``.
    The user id is stored on Flask's ``g`` object by the decorator.
    """
    return getattr(g, "user_id", None)


def require_auth(f):
    """Decorator that requires a valid Supabase JWT Bearer token.

    On success, ``g.user_id`` is set to the Supabase user UUID (string).
    On failure, returns a 401 JSON error.
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        token = _extract_token()
        if not token:
            logger.warning("Auth failed: No Authorization header or not a Bearer token")
            return jsonify({"error": "Missing authorization token"}), 401

        logger.debug("Auth: got token (len=%d, start=%s...)", len(token), token[:20])
        payload = decode_token(token)
        if payload is None:
            logger.warning("Auth failed: Token decode returned None (invalid/expired JWT)")
            return jsonify({"error": "Invalid or expired token"}), 401

        g.user_id = payload.get("sub")
        if not g.user_id:
            logger.warning("Auth failed: Token decoded but missing 'sub' claim")
            return jsonify({"error": "Token missing user identity"}), 401

        logger.debug("Auth success: user_id=%s", g.user_id)
        return f(*args, **kwargs)

    return decorated


def optional_auth(f):
    """Decorator that optionally extracts user info from a Bearer token.

    If a valid token is present, ``g.user_id`` is populated.  If absent or
    invalid, ``g.user_id`` is ``None`` and the request proceeds anyway.
    Useful for endpoints that behave slightly differently when authenticated
    (e.g. show the user's own scored matches alongside public data).
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        token = _extract_token()
        if token:
            logger.debug("optional_auth: token present (len=%d)", len(token))
            payload = decode_token(token)
            if payload:
                g.user_id = payload.get("sub")
                logger.debug("optional_auth: user_id=%s", g.user_id)
            else:
                logger.warning("optional_auth: token found but decode failed")
        else:
            logger.debug("optional_auth: no token in request")
        return f(*args, **kwargs)

    return decorated
