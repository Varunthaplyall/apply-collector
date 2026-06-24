"""
Vercel Serverless Function entry point for the Flask app.

On Vercel, this file at api/index.py is deployed as a Python Serverless Function
and handles all /api/* requests (configured via vercel.json rewrites).

Key differences from the standalone Flask server:
  - No Playwright or sentence-transformers (too large for Vercel free tier).
  - Embedding-based scoring gracefully falls back to keyword matching.
  - Background collection runs may exceed the 10s function timeout.
    Use the dashboard for viewing data; run collection locally or on Render.
"""

import sys
from pathlib import Path

# Ensure the project root is on sys.path so data_collection imports work
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Pre-load environment variables from .env (Vercel sets them as env vars,
# but .env is there for local parity)
from dotenv import load_dotenv
load_dotenv(_PROJECT_ROOT / ".env")

from web.app import app
from data_collection.database import init_db

# Initialize database tables on cold start
init_db()
