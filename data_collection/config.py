import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUTS_DIR = BASE_DIR / "outputs"

# Supabase / PostgreSQL
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")
CONFIG_PATH = BASE_DIR / "target_companies.json"

# Ensure required dirs exist
for d in (DATA_DIR, OUTPUTS_DIR):
    d.mkdir(parents=True, exist_ok=True)
