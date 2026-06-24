import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUTS_DIR = BASE_DIR / "outputs"
SAMPLES_DIR = BASE_DIR / "samples"

# Supabase / PostgreSQL
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Legacy SQLite path (kept for fallback/testing)
DB_PATH = DATA_DIR / "jobs.db"
CONFIG_PATH = BASE_DIR / "target_companies.json"

# Ensure required dirs exist
for d in (DATA_DIR, OUTPUTS_DIR):
    d.mkdir(parents=True, exist_ok=True)
