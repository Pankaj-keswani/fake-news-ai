"""Central configuration. Every value can be overridden with an environment variable (or backend/.env)."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"

# Load backend/.env no matter which folder the server is started from.
load_dotenv(BASE_DIR / ".env")


def _str(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip().strip('"').strip("'")


def _int(name: str, default: int) -> int:
    try:
        return int(_str(name, str(default)))
    except ValueError:
        return default


def _bool(name: str, default: bool) -> bool:
    return _str(name, "1" if default else "0").lower() in ("1", "true", "yes", "on")


# --- environment ---------------------------------------------------------------
# Vercel sets VERCEL=1, so deployments there count as production automatically.
ON_VERCEL = bool(os.getenv("VERCEL"))
APP_ENV = _str("APP_ENV", "production" if ON_VERCEL else "development").lower()
IS_PRODUCTION = APP_ENV == "production"
DEBUG = _bool("FLASK_DEBUG", not IS_PRODUCTION)
PORT = _int("PORT", 5000)

# --- AI (Groq) -----------------------------------------------------------------
GROQ_API_KEY = _str("GROQ_API_KEY")
# Main model that decides the verdict. ("llama-3.1-8b-instant" was retired on Groq.)
GROQ_MODEL = _str("GROQ_MODEL", "openai/gpt-oss-120b")
# Fast model for understanding the claim + fallback when the main model is busy/rate-limited.
GROQ_FAST_MODEL = _str("GROQ_FAST_MODEL", "openai/gpt-oss-20b")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# --- optional extra evidence -----------------------------------------------------
# Free key from https://developers.google.com/fact-check/tools/api (optional).
FACTCHECK_API_KEY = _str("FACTCHECK_API_KEY")

# --- limits & caching --------------------------------------------------------------
MAX_TEXT_LENGTH = _int("MAX_TEXT_LENGTH", 5000)
# Flask-Limiter syntax, several limits separated by ";"
RATE_LIMIT = _str("RATE_LIMIT", "8 per minute;80 per day")
CACHE_TTL_SECONDS = _int("CACHE_TTL_SECONDS", 6 * 60 * 60)
CACHE_MAX_ITEMS = _int("CACHE_MAX_ITEMS", 500)

# --- web ---------------------------------------------------------------------------
# Comma-separated list of extra origins allowed to call the API (only needed if the
# frontend is hosted on a different domain than the backend). Use "*" to allow all.
ALLOWED_ORIGINS = [o.strip() for o in _str("ALLOWED_ORIGINS").split(",") if o.strip()]
# Set to 1 when running behind a reverse proxy (Render, Railway, Nginx...) so rate
# limits use the real visitor IP instead of the proxy's IP.
TRUST_PROXY = _bool("TRUST_PROXY", IS_PRODUCTION)
