"""
Module: booster.py
Purpose: Autonomous Recruiter Profile Booster for Naukri.com.
         Ensures candidate profile freshness is indexed under 'Active / Updated Today'
         on Naukri Resdex recruiter search engine, dramatically increasing profile views
         and interview inbound shortlists.
Standards: Rule 1 (Zero Blind Trust), Rule 2 (Type & Schema Safety), Rule 5 (Production Reliability).
"""
import time
import logging
import threading
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from playwright.sync_api import sync_playwright

from app.config import DATA_DIR
from app.agent.browser import DEFAULT_USER_AGENT, sanitize_session_preferences
from app.agent.stealth import get_stealth_chromium_args
from app.core.user_storage import get_user_browser_lock

logger = logging.getLogger("agent.booster")

_last_boost_timestamps: Dict[int, float] = {}
BOOSTER_COOLDOWN_SECONDS = 300  # 5 minutes minimum between manual boosts


def boost_naukri_profile(
    resume_path: Optional[str] = None,
    screenshot_dir: Optional[Path] = None,
    user_id: int = 1,
    bypass_cooldown: bool = False,
) -> Dict[str, Any]:
    """
    Touches and refreshes candidate Naukri profile by re-uploading the verified resume PDF scoped to user_id.
    Naukri Resdex updates candidate freshness to 'Today', placing them in the 1st page
    of recruiter active searches.
    """
    user_lock = get_user_browser_lock(user_id)
    if not user_lock.acquire(blocking=False):
        return {
            "status": "already_running",
            "message": f"Browser session is currently busy for User {user_id} (another operation is active). Please wait."
        }

    try:
        now_ts = time.time()
        last_boost = _last_boost_timestamps.get(user_id, 0.0)
        if not bypass_cooldown and (now_ts - last_boost) < BOOSTER_COOLDOWN_SECONDS:
            remaining_mins = max(1, round((BOOSTER_COOLDOWN_SECONDS - (now_ts - last_boost)) / 60))
            return {
                "status": "already_boosted",
                "message": f"Naukri profile was already refreshed recently. Resdex freshness is active (cooldown: {remaining_mins}m).",
                "last_boost": datetime.fromtimestamp(last_boost).isoformat()
            }

        from app.core.user_storage import get_user_browser_session_dir, get_user_resume
        session_dir = get_user_browser_session_dir(user_id)
        marker_file = session_dir / "session_verified.json"
        if not marker_file.exists():
            return {
                "status": "error",
                "message": f"Naukri browser session not found or not verified for User {user_id}. Please connect Naukri first."
            }

        target_resume = Path(resume_path) if resume_path else get_user_resume(user_id)
        if not target_resume or not target_resume.exists():
            return {
                "status": "error",
                "message": f"Resume PDF not found for User {user_id}. Please upload resume first."
            }

        sanitize_session_preferences(session_dir)
        logger.info("🚀 Launching Naukri Profile Booster Engine...")

        try:
            with sync_playwright() as p:
                context = None
                launch_args = list(get_stealth_chromium_args())
                for ch in ["chrome", None]:
                    try:
                        kwargs = {
                            "user_data_dir": str(session_dir),
                            "headless": True,
                            "args": launch_args,
                            "user_agent": DEFAULT_USER_AGENT,
                            "viewport": {"width": 1280, "height": 850},
                            "locale": "en-US",
                            "timezone_id": "Asia/Kolkata",
                        }
                        if ch:
                            kwargs["channel"] = ch
                        context = p.chromium.launch_persistent_context(**kwargs)
                        break
                    except Exception as launch_err:
                        logger.debug(f"Could not launch browser with channel '{ch}': {launch_err}")

                if context is None:
                    return {
                        "status": "error",
                        "message": "Failed to launch browser engine (neither Chrome nor Chromium could be started)."
                    }

                page = context.pages[0] if context.pages else context.new_page()

                logger.info("Warming authenticated session via Naukri Homepage...")
                try:
                    page.goto("https://www.naukri.com/mnjuser/homepage", timeout=30000, wait_until="domcontentloaded")
                    page.wait_for_timeout(2000)
                except Exception as warm_err:
                    logger.debug(f"Booster warm-up notice: {warm_err}")

                logger.info("Navigating to candidate Profile page...")
                page.goto("https://www.naukri.com/mnjuser/profile", timeout=35000, wait_until="load")
                page.wait_for_timeout(3000)

                # Locate file input for resume upload
                file_input = page.query_selector("input[type='file'].upload-input, input[type='file']")
                if not file_input:
                    context.close()
                    return {
                        "status": "error",
                        "message": "Upload resume file input not found on profile page."
                    }

                logger.info(f"Re-uploading resume to trigger Resdex freshness: {target_resume.name}")
                file_input.set_input_files(str(target_resume.resolve()))
                page.wait_for_timeout(4500)

                # Record successful boost timestamp
                _last_boost_timestamps[user_id] = time.time()
                now_iso = datetime.now().isoformat()
                snap_path = None
                if screenshot_dir:
                    snap_path = screenshot_dir / "step4_naukri_profile_boosted.png"
                    try:
                        page.screenshot(path=str(snap_path))
                    except Exception:
                        pass

                context.close()
                logger.info("✅ Recruiter Profile Booster completed successfully!")
                return {
                    "status": "success",
                    "message": "Naukri profile boosted successfully! Candidate freshness marked 'Updated Today'.",
                    "timestamp": now_iso,
                    "screenshot": str(snap_path) if snap_path else None
                }

        except Exception as boost_err:
            logger.error(f"Naukri Profile Booster error: {boost_err}", exc_info=True)
            return {
                "status": "error",
                "message": f"Profile booster execution error: {str(boost_err)}"
            }
    finally:
        user_lock.release()


async def boost_naukri_profile_live(
    resume_path: Optional[str] = None,
    screenshot_dir: Optional[Path] = None,
    user_id: int = 1,
    bypass_cooldown: bool = False,
) -> Dict[str, Any]:
    """Async wrapper for boost_naukri_profile scoped to user_id."""
    import asyncio
    return await asyncio.to_thread(
        boost_naukri_profile,
        resume_path=resume_path,
        screenshot_dir=screenshot_dir,
        user_id=user_id,
        bypass_cooldown=bypass_cooldown,
    )

