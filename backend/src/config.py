import os
from pathlib import Path

# Repo root is 2 levels up from backend/src/
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("AIFP_DATA_DIR", REPO_ROOT / "backend" / ".local" / "data"))
MEDIA_DIR = Path(os.getenv("AIFP_MEDIA_DIR", REPO_ROOT / "backend" / ".local" / "media"))
DB_PATH = Path(os.getenv("AIFP_DB_PATH", DATA_DIR / "veo.db"))
MAX_UPLOAD_BYTES = int(os.getenv("AIFP_MAX_UPLOAD_BYTES", 8 * 1024 * 1024 * 1024))
READ_ONLY = os.getenv("AIFP_READ_ONLY", "0") == "1"
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "AIFP_CORS_ORIGINS",
        "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:8000,http://localhost:8000",
    ).split(",")
    if origin.strip()
]

DATA_DIR.mkdir(parents=True, exist_ok=True)
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
