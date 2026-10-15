"""
Module: config.py
Purpose: Central configuration, secrets management, and AI client initialization.
Standards: Rule 2 (Hardcore Security - Single Secret Boundary), Rule 3 (Low Code & High Accuracy).
"""
import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv
from google import genai

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
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'jobs.db'}")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is not set. Please add it to backend/.env")

# Initialize Gemini AI Client once globally (Claude Fix #1)
gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# CORS Whitelist for Frontend (Vite, Localhost, Mobile preview)
CORS_ORIGINS: List[str] = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# AI Generation defaults
DEFAULT_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
DEFAULT_PACING_SECONDS: float = 2.5
