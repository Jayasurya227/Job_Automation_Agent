"""
Module: user_storage.py
Purpose: Enterprise-Grade Multi-User Storage & Vault Architecture (Phase 2 Step 1).
Provides isolated directories and file paths per user:
  backend/data/users/{user_id}/
  ├── profile.json            # Candidate profile
  ├── uploaded_resume.pdf     # Master candidate resume
  ├── tailored_resumes/       # Tailored LaTeX & PDF resumes
  ├── browser_session/        # Isolated Chromium user data & Naukri cookies
  └── output/snapshots/       # Proof screenshots for candidate review
"""
import os
import shutil
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from app.config import DATA_DIR, BASE_DIR
from app.schemas.profile import CandidateProfile

logger = logging.getLogger("user_storage")

USERS_ROOT_DIR = DATA_DIR / "users"
USERS_ROOT_DIR.mkdir(parents=True, exist_ok=True)

# Legacy global paths for safe backward compatibility and initial seeding
LEGACY_GLOBAL_PROFILE = BASE_DIR / "profile.json"
LEGACY_GLOBAL_RESUME = DATA_DIR / "uploaded_resume.pdf"
LEGACY_GLOBAL_SESSION = DATA_DIR / "browser_session"
LEGACY_GLOBAL_INDEED_SESSION = DATA_DIR / "indeed_session"


def get_user_base_dir(user_id: int) -> Path:
    """Returns the dedicated root directory for a given user, creating it if needed."""
    user_dir = USERS_ROOT_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def get_user_profile_path(user_id: int) -> Path:
    """Returns path to the user's isolated profile.json."""
    return get_user_base_dir(user_id) / "profile.json"


def get_user_resume_path(user_id: int) -> Path:
    """Returns path to the user's isolated uploaded_resume.pdf."""
    return get_user_base_dir(user_id) / "uploaded_resume.pdf"


def get_user_browser_session_dir(user_id: int) -> Path:
    """Returns path to the user's isolated Naukri Chromium session folder."""
    session_dir = get_user_base_dir(user_id) / "browser_session"
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def get_user_indeed_session_dir(user_id: int) -> Path:
    """Returns path to the user's isolated Indeed Chromium session folder."""
    session_dir = get_user_base_dir(user_id) / "indeed_session"
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def get_user_snapshots_dir(user_id: int) -> Path:
    """Returns path to the user's proof screenshots folder."""
    snapshots_dir = get_user_base_dir(user_id) / "output" / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    return snapshots_dir


def get_user_tailored_resumes_dir(user_id: int) -> Path:
    """Returns path to the user's generated tailored resumes folder."""
    tailored_dir = get_user_base_dir(user_id) / "tailored_resumes"
    tailored_dir.mkdir(parents=True, exist_ok=True)
    return tailored_dir


def ensure_user_storage(user_id: int) -> Dict[str, Path]:
    """
    Initializes and ensures all directories exist for a given user.
    If user_id == 1 and files are not yet in users/1/, safely auto-migrates User 1's
    existing profile, resume, and Naukri browser session without deleting originals.
    """
    base_dir = get_user_base_dir(user_id)
    profile_path = get_user_profile_path(user_id)
    resume_path = get_user_resume_path(user_id)
    session_dir = get_user_browser_session_dir(user_id)
    indeed_session_dir = get_user_indeed_session_dir(user_id)
    snapshots_dir = get_user_snapshots_dir(user_id)
    tailored_dir = get_user_tailored_resumes_dir(user_id)

    # User 1 Safe Auto-Migration (Zero Data Loss)
    if user_id == 1:
        # 1. Profile migration
        if not profile_path.exists() and LEGACY_GLOBAL_PROFILE.exists():
            try:
                shutil.copy2(LEGACY_GLOBAL_PROFILE, profile_path)
                logger.info("Safely migrated User 1 profile.json to users/1/profile.json")
            except Exception as e:
                logger.warning(f"Profile migration notice for User 1: {e}")

        # 2. Resume migration
        if not resume_path.exists() and LEGACY_GLOBAL_RESUME.exists():
            try:
                shutil.copy2(LEGACY_GLOBAL_RESUME, resume_path)
                logger.info("Safely migrated User 1 uploaded_resume.pdf to users/1/uploaded_resume.pdf")
            except Exception as e:
                logger.warning(f"Resume migration notice for User 1: {e}")

        # 3. Naukri Browser Session migration
        try:
            has_existing_session_files = session_dir.exists() and any(session_dir.iterdir())
            if not has_existing_session_files and LEGACY_GLOBAL_SESSION.exists() and any(LEGACY_GLOBAL_SESSION.iterdir()):
                for item in LEGACY_GLOBAL_SESSION.iterdir():
                    dest = session_dir / item.name
                    if item.is_dir() and not dest.exists():
                        shutil.copytree(item, dest)
                    elif item.is_file() and not dest.exists():
                        shutil.copy2(item, dest)
                logger.info("Safely migrated User 1 Naukri browser_session into users/1/browser_session/")
        except Exception as e:
            logger.warning(f"Browser session migration notice for User 1: {e}")

        # 4. Indeed Browser Session migration
        try:
            has_existing_indeed_files = indeed_session_dir.exists() and any(indeed_session_dir.iterdir())
            if not has_existing_indeed_files and LEGACY_GLOBAL_INDEED_SESSION.exists() and any(LEGACY_GLOBAL_INDEED_SESSION.iterdir()):
                for item in LEGACY_GLOBAL_INDEED_SESSION.iterdir():
                    dest = indeed_session_dir / item.name
                    if item.is_dir() and not dest.exists():
                        shutil.copytree(item, dest)
                    elif item.is_file() and not dest.exists():
                        shutil.copy2(item, dest)
                logger.info("Safely migrated User 1 Indeed session into users/1/indeed_session/")
        except Exception as e:
            logger.warning(f"Indeed session migration notice for User 1: {e}")

    return {
        "base_dir": base_dir,
        "profile_path": profile_path,
        "resume_path": resume_path,
        "browser_session_dir": session_dir,
        "indeed_session_dir": indeed_session_dir,
        "snapshots_dir": snapshots_dir,
        "tailored_resumes_dir": tailored_dir,
    }


def load_user_profile(user_id: int, db=None) -> CandidateProfile:
    """
    Loads candidate profile for user_id with 100% isolation.
    - If user has existing profile.json in users/{user_id}/, loads it.
    - If user_id == 1 and users/1/profile.json missing, auto-migrates from legacy profile.json.
    - If brand new user without profile.json, seeds a clean default profile populated with user's name/email.
    """
    ensure_user_storage(user_id)
    profile_path = get_user_profile_path(user_id)

    if profile_path.exists():
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return CandidateProfile(**data)
        except Exception as e:
            logger.error(f"Error reading profile for user {user_id}: {e}")

    # Fallback / Seed default profile for new candidate
    candidate_name = f"Candidate {user_id}"
    candidate_email = ""
    if db is not None:
        try:
            from app.db.models import User
            user_record = db.query(User).filter(User.id == user_id).first()
            if user_record:
                candidate_name = user_record.full_name or candidate_name
                candidate_email = user_record.email or candidate_email
        except Exception:
            pass

    default_profile_data = {
        "personal_info": {
            "name": candidate_name,
            "email": candidate_email,
            "phone": "",
            "location": "India",
            "linkedin_url": "",
            "github_url": "",
            "portfolio_url": ""
        },
        "preferences": {
            "target_roles": ["Python Developer", "Junior AI Engineer"],
            "preferred_locations": ["Remote", "Bengaluru", "Hyderabad"],
            "work_modes": ["Remote", "Hybrid"],
            "min_expected_salary": "Standard Industry CTC",
            "notice_period_days": 0,
            "freshness_days": 1,
            "autopilot_enabled": False,
            "autopilot_auto_apply_score": 80,
            "autopilot_max_daily_apps": 12,
            "autopilot_run_hour": 9,
            "autopilot_run_minute": 0
        },
        "technical_skills": {
            "programming_languages": [],
            "frameworks_and_libraries": [],
            "ai_and_ml": [],
            "databases": [],
            "tools_and_platforms": []
        },
        "experience": [],
        "projects": [],
        "education": [],
        "application_answers": {
            "immediate_joiner": True,
            "willing_to_relocate": True,
            "years_of_experience": 1.0,
            "work_authorization": "Authorized to work in India",
            "custom_qa": {}
        }
    }
    default_profile = CandidateProfile(**default_profile_data)
    save_user_profile(user_id, default_profile)
    return default_profile


def save_user_profile(user_id: int, profile: CandidateProfile) -> CandidateProfile:
    """
    Saves candidate profile atomically with zero-corruption guarantee.
    Writes to profile.json.tmp first, flushes, fsyncs, and replaces atomically via os.replace.
    """
    ensure_user_storage(user_id)
    profile_path = get_user_profile_path(user_id)
    temp_path = profile_path.with_suffix(".json.tmp")

    data = profile.model_dump()
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())

    os.replace(temp_path, profile_path)
    logger.info(f"User {user_id} profile saved atomically to {profile_path}")
    return profile


def save_user_resume(user_id: int, filename: str, contents: bytes) -> Path:
    """
    Saves uploaded master resume PDF into user's private vault atomically.
    Validates PDF header (%PDF) and enforces strict per-user boundaries.
    """
    if not contents or not contents.startswith(b"%PDF"):
        raise ValueError("Invalid PDF format: file must begin with %PDF magic bytes.")

    ensure_user_storage(user_id)
    resume_path = get_user_resume_path(user_id)
    temp_path = resume_path.with_suffix(".pdf.tmp")

    with open(temp_path, "wb") as f:
        f.write(contents)
        f.flush()
        os.fsync(f.fileno())

    os.replace(temp_path, resume_path)
    logger.info(f"User {user_id} resume saved atomically to {resume_path} ({len(contents)} bytes)")
    return resume_path


def get_user_resume(user_id: int) -> Optional[Path]:
    """Returns path to user's uploaded resume if present and non-empty, else None."""
    ensure_user_storage(user_id)
    resume_path = get_user_resume_path(user_id)
    if resume_path.exists() and resume_path.stat().st_size > 0:
        return resume_path
    return None


# -----------------------------------------------------------------------------
# Centralized Per-User Browser Session Mutex Locks (Chromium Singleton Guard)
# -----------------------------------------------------------------------------
import threading
import asyncio
from collections import defaultdict
from contextlib import contextmanager, asynccontextmanager

_user_browser_locks: Dict[int, threading.Lock] = defaultdict(threading.Lock)
_global_lock_registry_lock = threading.Lock()


def get_user_browser_lock(user_id: int) -> threading.Lock:
    """
    Returns the process-wide mutual exclusion lock for a specific user's browser session directory.
    Guarantees thread-safe access to Chromium user_data_dir across all workers (booster, applier, auth, scraper).
    """
    with _global_lock_registry_lock:
        return _user_browser_locks[user_id]


@contextmanager
def user_browser_lock(user_id: int, blocking: bool = True, timeout: float = 60.0):
    """
    Synchronous context manager for acquiring a user's browser session lock.
    Used by synchronous Playwright worker threads (applier.py, booster.py, scraper.py).
    """
    lock = get_user_browser_lock(user_id)
    acquired = lock.acquire(blocking=blocking, timeout=timeout)
    if not acquired:
        raise BlockingIOError(f"User {user_id}'s browser session is currently locked by another active operation.")
    try:
        yield lock
    finally:
        lock.release()


@asynccontextmanager
async def async_user_browser_lock(user_id: int, timeout: float = 60.0):
    """
    Asynchronous context manager for acquiring a user's browser session lock without blocking the event loop.
    Used by async Playwright operations (headless_auth.py, browser.py).
    """
    lock = get_user_browser_lock(user_id)
    acquired = await asyncio.to_thread(lock.acquire, True, timeout)
    if not acquired:
        raise BlockingIOError(f"Timeout waiting for User {user_id}'s browser session lock.")
    try:
        yield lock
    finally:
        lock.release()


# -----------------------------------------------------------------------------
# Persistent Workflow Session Storage (Anti-Data-Loss & Multi-Worker State)
# -----------------------------------------------------------------------------
def get_user_workflow_sessions_dir(user_id: int) -> Path:
    """Returns dedicated directory for pending workflow sessions scoped to user_id."""
    sessions_dir = get_user_base_dir(user_id) / "workflow_sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    return sessions_dir


def save_workflow_session(user_id: int, thread_id: str, state: Dict[str, Any]) -> Path:
    """
    Persists pending review gateway workflow state to user's isolated storage atomically.
    Survives server restarts and enables seamless multi-worker cloud execution.
    """
    sessions_dir = get_user_workflow_sessions_dir(user_id)
    session_file = sessions_dir / f"{thread_id}.json"
    temp_file = sessions_dir / f"{thread_id}.tmp"

    clean_state: Dict[str, Any] = {}
    for k, v in state.items():
        try:
            json.dumps({k: v})
            clean_state[k] = v
        except Exception:
            clean_state[k] = str(v)

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(clean_state, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())

    os.replace(temp_file, session_file)
    logger.info(f"User {user_id} workflow session '{thread_id}' saved atomically to {session_file}")
    return session_file


def get_workflow_session(thread_id: str, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """
    Retrieves pending workflow session state by thread_id.
    If user_id is provided, searches strictly in user's vault.
    If user_id is None, searches across all vaults for ownership resolution.
    """
    if user_id is not None:
        session_file = get_user_workflow_sessions_dir(user_id) / f"{thread_id}.json"
        if session_file.exists():
            try:
                return json.loads(session_file.read_text(encoding="utf-8"))
            except Exception as e:
                logger.error(f"Failed to read session file {session_file}: {e}")
                return None
        return None

    if USERS_ROOT_DIR.exists():
        for u_dir in USERS_ROOT_DIR.iterdir():
            if u_dir.is_dir():
                s_file = u_dir / "workflow_sessions" / f"{thread_id}.json"
                if s_file.exists():
                    try:
                        return json.loads(s_file.read_text(encoding="utf-8"))
                    except Exception:
                        return None
    return None


def delete_workflow_session(thread_id: str, user_id: Optional[int] = None) -> bool:
    """Removes a completed or resumed workflow session file."""
    deleted = False
    if user_id is not None:
        session_file = get_user_workflow_sessions_dir(user_id) / f"{thread_id}.json"
        if session_file.exists():
            try:
                session_file.unlink()
                deleted = True
            except Exception as e:
                logger.warning(f"Failed to delete session file {session_file}: {e}")
        return deleted

    if USERS_ROOT_DIR.exists():
        for u_dir in USERS_ROOT_DIR.iterdir():
            if u_dir.is_dir():
                s_file = u_dir / "workflow_sessions" / f"{thread_id}.json"
                if s_file.exists():
                    try:
                        s_file.unlink()
                        deleted = True
                    except Exception:
                        pass
    return deleted



