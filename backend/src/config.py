import os
from pathlib import Path

# Repo root is 2 levels up from backend/src/
REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_env_file(path: Path):
    if not path.is_file():
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass


# Load script configs (base then local machine overrides)
_load_env_file(REPO_ROOT / "scripts" / "config.env")
_load_env_file(REPO_ROOT / "scripts" / "config.local.env")

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

# Cloudflare R2 / Pages settings
CF_ACCOUNT_ID = os.getenv("CF_ACCOUNT_ID", "").strip()
CF_R2_ACCESS_KEY_ID = os.getenv("CF_R2_ACCESS_KEY_ID", "").strip()
CF_R2_SECRET_ACCESS_KEY = os.getenv("CF_R2_SECRET_ACCESS_KEY", "").strip()
CF_R2_BUCKET_NAME = os.getenv("CF_R2_BUCKET_NAME", "aifp-media").strip()
CF_PUBLIC_BASE_URL = os.getenv("CF_PUBLIC_BASE_URL", "https://focusplay.pages.dev").strip().rstrip("/")
CF_R2_CUSTOM_DOMAIN = os.getenv("CF_R2_CUSTOM_DOMAIN", "").strip().rstrip("/")
CLOUD_EXPORT_DIR = Path(os.getenv("AIFP_CLOUD_EXPORT_DIR", REPO_ROOT / "backend" / ".local" / "cloud_export"))

DATA_DIR.mkdir(parents=True, exist_ok=True)
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
CLOUD_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
