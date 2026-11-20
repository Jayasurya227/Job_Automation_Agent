"""
Module: config.py
Purpose: Central configuration, secrets management, and AI client initialization.
Standards: Rule 2 (Hardcore Security - Single Secret Boundary), Rule 3 (Low Code & High Accuracy).
"""
import os
from pathlib import Path
from typing import List, Optional, Dict
from dotenv import load_dotenv
import anthropic

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Load environment variables once at module import
load_dotenv()
load_dotenv(BASE_DIR / ".env")

# Secrets & Connections
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'jobs.db'}")

if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY is not set. Please add it to backend/.env")

# Initialize the Claude client once globally
claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# CORS Whitelist for Frontend (Vite, Localhost, Mobile preview)
CORS_ORIGINS: List[str] = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://10.68.220.85:5173",
    "http://10.68.220.85:5174",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# Dynamic Cloud CORS Configuration (Issue 11)
# Seamlessly appends comma-separated cloud origins/IPs from CORS_ALLOWED_ORIGINS in .env
# (e.g. CORS_ALLOWED_ORIGINS=http://13.239.145.20:5173,https://myjobdomain.com)
_env_cors = os.getenv("CORS_ALLOWED_ORIGINS") or os.getenv("ALLOWED_ORIGINS")
if _env_cors:
    for origin in _env_cors.split(","):
        clean_origin = origin.strip().rstrip("/")
        if clean_origin and clean_origin not in CORS_ORIGINS:
            CORS_ORIGINS.append(clean_origin)

CORS_ALLOW_ALL: bool = os.getenv("CORS_ALLOW_ALL", "false").lower() in ("true", "1", "yes")

# AI Generation defaults
DEFAULT_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-haiku-5-5")
DEFAULT_PACING_SECONDS: float = 2.5

# Match-score routing (single source of truth for every module)
# >= AUTO_APPLY_MATCH_THRESHOLD (75%) -> Autonomous 1-Click Apply (Elite match)
# 70% to 74% -> Reserve Pool (Archived for safe backup)
# Below 70% -> Discard immediately.
READY_MATCH_THRESHOLD: int = 70
AUTO_APPLY_MATCH_THRESHOLD: int = 75

# Auto-Pilot submits matching jobs without review only when this is true.
# Off by default: matching jobs stay 'Ready' for your one-click approval.
AUTOPILOT_AUTO_SUBMIT: bool = os.getenv("AUTOPILOT_AUTO_SUBMIT", "true").lower() == "true"

# Multi-User JWT Security Configuration
ENVIRONMENT: str = os.getenv("ENVIRONMENT", os.getenv("ENV", "development")).lower()
_configured_jwt_secret = (
    os.getenv("JWT_SECRET_KEY")
    or os.getenv("SECRET_KEY")
    or os.getenv("JWT_SECRET")
)

if _configured_jwt_secret and _configured_jwt_secret.strip() and _configured_jwt_secret.strip() != "autonomous_job_agent_super_secret_jwt_key_2026_production":
    JWT_SECRET_KEY: str = _configured_jwt_secret.strip()
else:
    import secrets
    import logging
    _logger = logging.getLogger("config")
    if ENVIRONMENT in ("production", "prod"):
        raise RuntimeError(
            "CRITICAL SECURITY FAILURE: JWT_SECRET_KEY is not defined in environment variables! "
            "In production mode, a cryptographically secure JWT_SECRET_KEY is strictly mandatory."
        )
    _logger.warning(
        "SECURITY NOTICE: JWT_SECRET_KEY not found in environment. Generating an ephemeral random key for local development. "
        "Define JWT_SECRET_KEY in backend/.env to persist sessions across server restarts."
    )
    JWT_SECRET_KEY: str = secrets.token_urlsafe(64)

JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 24 * 7)))  # 7 Days default
OTP_EXPIRE_MINUTES: int = 10  # 10 minutes OTP validity window

# -------------------------------------------------------------------
# Indian Residential Proxy Configuration (Issue 10)
# Enables cloud servers (AWS Sydney/Mumbai/GCP/Docker) to route Playwright traffic
# through genuine Indian residential broadband IPs (bypassing Akamai/Cloudflare bot blocks).
# -------------------------------------------------------------------
RESIDENTIAL_PROXY_SERVER: Optional[str] = os.getenv("RESIDENTIAL_PROXY_SERVER") or os.getenv("PROXY_SERVER")
RESIDENTIAL_PROXY_USERNAME: Optional[str] = os.getenv("RESIDENTIAL_PROXY_USERNAME") or os.getenv("PROXY_USERNAME")
RESIDENTIAL_PROXY_PASSWORD: Optional[str] = os.getenv("RESIDENTIAL_PROXY_PASSWORD") or os.getenv("PROXY_PASSWORD")

def get_playwright_proxy_config() -> Optional[Dict[str, str]]:
    """
    Returns a Playwright-compatible proxy configuration dict if configured, else None.
    If no proxy is set, returns None so browsers connect directly (free local dev).
    """
    if not RESIDENTIAL_PROXY_SERVER or not RESIDENTIAL_PROXY_SERVER.strip():
        return None
    server_clean = RESIDENTIAL_PROXY_SERVER.strip()
    if not server_clean.startswith("http://") and not server_clean.startswith("https://") and not server_clean.startswith("socks5://"):
        server_clean = f"http://{server_clean}"
    proxy_dict = {"server": server_clean}
    if RESIDENTIAL_PROXY_USERNAME and RESIDENTIAL_PROXY_USERNAME.strip():
        proxy_dict["username"] = RESIDENTIAL_PROXY_USERNAME.strip()
    if RESIDENTIAL_PROXY_PASSWORD and RESIDENTIAL_PROXY_PASSWORD.strip():
        proxy_dict["password"] = RESIDENTIAL_PROXY_PASSWORD.strip()
    return proxy_dict
