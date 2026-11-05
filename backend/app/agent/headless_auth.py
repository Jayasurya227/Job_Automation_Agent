"""
Module: headless_auth.py
Purpose: Enterprise-grade Headless Authentication Engine for Mobile Portal Connection.
Standards: Supports silent background login with Playwright stealth, automatic OTP detection,
           and in-memory session keep-alive for mobile interactive verification.
Part of Dual-Mode Portal Connection (Mobile OTP + Laptop Browser).
"""

import sys
import time
import uuid
import json
import random
import logging
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Any, Tuple
from dataclasses import dataclass

from playwright.sync_api import sync_playwright, BrowserContext, Page, Playwright

# Safe Windows stdout encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

backend_dir = Path(__file__).resolve().parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.config import DATA_DIR
from app.agent.browser import (
    DEFAULT_SESSION_DIR,
    sanitize_session_preferences,
    DEFAULT_USER_AGENT,
)
from app.agent.stealth import get_stealth_chromium_args, build_stealth_js
from login_session import verify_portal_login

logger = logging.getLogger("agent.headless_auth")


@dataclass
class PendingAuthSession:
    """Tracks an active headless browser session waiting for user OTP."""
    session_id: str
    portal: str
    identifier: str
    playwright: Playwright
    context: BrowserContext
    page: Page
    created_at: float
    timeout_sec: float = 300.0  # 5 minutes keep-alive for user to enter SMS OTP


class HeadlessAuthManager:
    """
    Manages headless browser instances for mobile portal login & OTP validation.
    Runs synchronously in dedicated worker threads to guarantee 100% stability
    across Windows asyncio environments.
    """

    def __init__(self, session_dir: Optional[Path] = None):
        self.session_dir = Path(session_dir or DEFAULT_SESSION_DIR)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self._active_sessions: Dict[str, PendingAuthSession] = {}

    def cleanup_expired_sessions(self) -> None:
        """Closes and removes any abandoned login sessions older than timeout_sec."""
        now = time.time()
        expired_ids = [
            sid for sid, s in self._active_sessions.items()
            if now - s.created_at > s.timeout_sec
        ]
        for sid in expired_ids:
            logger.info(f"Closing expired headless auth session {sid}")
            self._close_session(sid)

    def _close_session(self, session_id: str) -> None:
        """Safely closes Playwright context and frees resources."""
        session = self._active_sessions.pop(session_id, None)
        if session:
            try:
                session.context.close()
            except Exception as e:
                logger.debug(f"Notice closing context: {e}")
            try:
                session.playwright.stop()
            except Exception as e:
                logger.debug(f"Notice stopping playwright: {e}")

    def start_naukri_login(
        self,
        identifier: str,
        password: Optional[str] = None,
        use_otp_mode: bool = False,
        custom_session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Initiates headless Naukri login.
        Returns:
            - {"status": "SUCCESS", "message": ...} if logged in directly
            - {"status": "OTP_REQUIRED", "session_id": ..., "message": ...} if OTP challenge detected
            - {"status": "ERROR", "message": ...} if credentials failed or error occurred
        """
        self.cleanup_expired_sessions()
        session_id = custom_session_id or str(uuid.uuid4())
        sanitize_session_preferences(self.session_dir)

        p = None
        context = None
        try:
            p = sync_playwright().start()
            launch_args = list(get_stealth_chromium_args())
            launch_args.extend(["--no-first-run", "--no-default-browser-check"])

            launch_kwargs = {
                "user_data_dir": str(self.session_dir),
                "headless": True,
                "args": launch_args,
                "user_agent": DEFAULT_USER_AGENT,
                "viewport": {"width": 1280, "height": 800},
                "locale": "en-US",
                "timezone_id": "Asia/Kolkata",
                "ignore_https_errors": True,
            }

            for ch in ["chrome", "msedge", None]:
                try:
                    kw = dict(launch_kwargs)
                    if ch:
                        kw["channel"] = ch
                    context = p.chromium.launch_persistent_context(**kw)
                    break
                except Exception as e:
                    logger.debug(f"Could not launch channel={ch}: {e}")

            if not context:
                context = p.chromium.launch_persistent_context(**launch_kwargs)

            context.add_init_script(build_stealth_js())
            page = context.pages[0] if context.pages else context.new_page()

            logger.info("Navigating to https://www.naukri.com/nlogin/login ...")
            page.goto("https://www.naukri.com/nlogin/login", wait_until="domcontentloaded", timeout=45000)
            time.sleep(2)

            # Check if user is already logged in with existing session
            cookies = context.cookies()
            is_logged_in, _ = asyncio.run(verify_portal_login("Naukri", page, cookies)) if "nlogin" not in page.url else (False, "")
            if is_logged_in:
                self._save_session_marker(page, cookies)
                context.close()
                p.stop()
                return {
                    "status": "SUCCESS",
                    "message": "Already authenticated into Naukri candidate session.",
                    "portal": "naukri",
                }

            # Flow A: Password-based login (can trigger 2FA OTP)
            if password and not use_otp_mode:
                username_input = page.query_selector("#usernameField, input[placeholder*='Username'], input[placeholder*='Email']")
                password_input = page.query_selector("#passwordField, input[type='password']")
                submit_btn = page.query_selector("button[type='submit'], .loginButton, button:has-text('Login')")

                if not username_input or not password_input or not submit_btn:
                    context.close()
                    p.stop()
                    return {"status": "ERROR", "message": "Naukri login fields could not be found."}

                # Human-like typing
                username_input.click()
                time.sleep(0.2)
                username_input.fill("")
                for c in identifier:
                    username_input.type(c, delay=random.uniform(25, 75))
                time.sleep(0.4)

                password_input.click()
                time.sleep(0.2)
                password_input.fill("")
                for c in password:
                    password_input.type(c, delay=random.uniform(25, 75))
                time.sleep(0.5)

                submit_btn.click()
                logger.info("Submitted login credentials, awaiting challenge / response...")

                # Wait up to 10 seconds to check what page responds with
                for _ in range(10):
                    time.sleep(1)
                    curr_url = page.url.lower()

                    # 1. Check if direct login succeeded (redirected away from nlogin)
                    if "nlogin" not in curr_url and ("mnjuser" in curr_url or "mynaukri" in curr_url or "naukri.com" in curr_url):
                        cookies = context.cookies()
                        auth_ok, reason = asyncio.run(verify_portal_login("Naukri", page, cookies))
                        if auth_ok:
                            self._save_session_marker(page, cookies)
                            context.close()
                            p.stop()
                            return {
                                "status": "SUCCESS",
                                "message": "Successfully logged into Naukri candidate profile!",
                                "portal": "naukri",
                            }

                    # 2. Check for credential errors
                    err_el = page.query_selector(".server-err, .err, .error-message, [class*='errorMessage']")
                    if err_el and err_el.is_visible():
                        err_text = err_el.inner_text().strip()
                        if err_text:
                            context.close()
                            p.stop()
                            return {"status": "ERROR", "message": f"Naukri Login Failed: {err_text}"}

                    # 3. Check for OTP Challenge Screen
                    otp_input = page.query_selector(
                        "input[placeholder*='OTP' i], "
                        "input[name*='otp' i], "
                        ".otp-input, "
                        "input[type='tel'][maxlength='6'], "
                        "input[type='number'][maxlength='6']"
                    )
                    otp_screen_text = page.query_selector("text='Enter OTP', text='Verification Code', text='OTP sent'")
                    if otp_input or otp_screen_text:
                        logger.info("OTP Challenge detected on Naukri!")
                        # Keep session alive in memory
                        self._active_sessions[session_id] = PendingAuthSession(
                            session_id=session_id,
                            portal="naukri",
                            identifier=identifier,
                            playwright=p,
                            context=context,
                            page=page,
                            created_at=time.time(),
                        )
                        return {
                            "status": "OTP_REQUIRED",
                            "session_id": session_id,
                            "portal": "naukri",
                            "message": "Naukri sent a 6-digit verification OTP to your registered mobile number.",
                        }

            # Flow B: Direct OTP Login Mode (Use OTP to Login button)
            if use_otp_mode or not password:
                otp_toggle = page.query_selector("button:has-text('Use OTP'), .otp-link, span:has-text('Use OTP')")
                if otp_toggle:
                    otp_toggle.click()
                    time.sleep(1.5)

                mobile_input = page.query_selector("input[type='tel'], input[placeholder*='mobile' i], #usernameField")
                get_otp_btn = page.query_selector("button:has-text('Get OTP'), button[type='submit']")

                if mobile_input and get_otp_btn:
                    mobile_input.click()
                    mobile_input.fill("")
                    for c in identifier:
                        mobile_input.type(c, delay=random.uniform(25, 75))
                    time.sleep(0.5)
                    get_otp_btn.click()
                    logger.info(f"Requested OTP for {identifier}...")
                    time.sleep(2)

                    # Keep session alive in memory
                    self._active_sessions[session_id] = PendingAuthSession(
                        session_id=session_id,
                        portal="naukri",
                        identifier=identifier,
                        playwright=p,
                        context=context,
                        page=page,
                        created_at=time.time(),
                    )
                    return {
                        "status": "OTP_REQUIRED",
                        "session_id": session_id,
                        "portal": "naukri",
                        "message": f"Naukri sent an OTP to {identifier}.",
                    }

            # Fallback if neither succeeded nor showed OTP within initial window
            # Keep open just in case OTP is loading slowly
            self._active_sessions[session_id] = PendingAuthSession(
                session_id=session_id,
                portal="naukri",
                identifier=identifier,
                playwright=p,
                context=context,
                page=page,
                created_at=time.time(),
            )
            return {
                "status": "OTP_REQUIRED",
                "session_id": session_id,
                "portal": "naukri",
                "message": "Verification code requested. Please enter the OTP sent to your phone.",
            }

        except Exception as e:
            logger.error(f"Error starting headless Naukri login: {e}")
            if context:
                try:
                    context.close()
                except Exception:
                    pass
            if p:
                try:
                    p.stop()
                except Exception:
                    pass
            return {"status": "ERROR", "message": f"Headless login error: {str(e)}"}

    def verify_naukri_otp(self, session_id: str, otp: str) -> Dict[str, Any]:
        """
        Submits the user's OTP to the active headless browser session.
        Completes authentication and saves verified cookies.
        """
        clean_otp = otp.strip().replace(" ", "").replace("-", "")
        if not clean_otp or len(clean_otp) < 4:
            return {"status": "ERROR", "message": "Invalid OTP format. Please enter a valid 6-digit OTP."}

        session = self._active_sessions.get(session_id)
        if not session:
            return {
                "status": "ERROR",
                "message": "Login session expired or not found. Please click Connect to request a fresh OTP.",
            }

        page = session.page
        context = session.context
        p = session.playwright

        try:
            logger.info(f"Entering OTP for session {session_id}...")

            # Multiple selectors for Naukri OTP input box
            otp_selectors = [
                "input[placeholder*='OTP' i]",
                "input[name*='otp' i]",
                "input.otp-input",
                "input[type='tel']",
                "input[type='number']",
                "input[maxlength='6']",
                "form input[type='text']",
            ]

            otp_input = None
            for sel in otp_selectors:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    otp_input = el
                    break

            # Check for multiple 1-digit OTP input boxes (e.g. 6 separate inputs)
            digit_inputs = page.query_selector_all(".otp-box input, input.digit-input, [class*='otp'] input")
            if len(digit_inputs) == 6 and len(clean_otp) == 6:
                for idx, digit in enumerate(clean_otp):
                    digit_inputs[idx].click()
                    digit_inputs[idx].fill(digit)
                    time.sleep(0.08)
            elif otp_input:
                otp_input.click()
                otp_input.fill("")
                for c in clean_otp:
                    otp_input.type(c, delay=random.uniform(30, 80))
            else:
                # Fallback: type directly onto page
                page.keyboard.type(clean_otp, delay=50)

            time.sleep(0.5)

            # Click verify / submit button
            verify_btn_selectors = [
                "button:has-text('Verify')",
                "button:has-text('Submit')",
                "button:has-text('Login')",
                "button[type='submit']",
                ".submit-btn",
                ".verify-btn",
            ]
            for btn_sel in verify_btn_selectors:
                btn = page.query_selector(btn_sel)
                if btn and btn.is_visible():
                    btn.click()
                    logger.info(f"Clicked OTP submit button ({btn_sel})")
                    break

            # Wait for redirect and session cookie capture
            for _ in range(12):
                time.sleep(1)
                curr_url = page.url.lower()

                # Check if authenticated
                cookies = context.cookies()
                auth_ok, auth_reason = asyncio.run(verify_portal_login("Naukri", page, cookies))
                if auth_ok:
                    self._save_session_marker(page, cookies)
                    logger.info(f"✅ OTP Verified successfully for {session.identifier}!")
                    self._close_session(session_id)
                    return {
                        "status": "SUCCESS",
                        "message": "Naukri account successfully connected and verified via Mobile OTP!",
                        "portal": "naukri",
                        "cookie_count": len(cookies),
                    }

                # Check for explicit OTP invalid error
                err_el = page.query_selector(".server-err, .err, [class*='error' i], text='Invalid OTP', text='Incorrect OTP'")
                if err_el and err_el.is_visible():
                    err_msg = err_el.inner_text().strip()
                    if err_msg and ("otp" in err_msg.lower() or "invalid" in err_msg.lower() or "incorrect" in err_msg.lower()):
                        # Keep session alive so user can re-try
                        return {"status": "ERROR", "message": f"Verification failed: {err_msg}"}

            # Final check before giving up
            cookies = context.cookies()
            auth_ok, auth_reason = asyncio.run(verify_portal_login("Naukri", page, cookies))
            if auth_ok:
                self._save_session_marker(page, cookies)
                self._close_session(session_id)
                return {
                    "status": "SUCCESS",
                    "message": "Naukri account successfully connected!",
                    "portal": "naukri",
                    "cookie_count": len(cookies),
                }

            return {
                "status": "ERROR",
                "message": f"OTP verification timed out or did not complete. (Status: {auth_reason})",
            }

        except Exception as e:
            logger.error(f"Error during OTP verification: {e}")
            return {"status": "ERROR", "message": f"Verification error: {str(e)}"}

    def _save_session_marker(self, page: Page, cookies: list[dict]) -> None:
        """Saves session_verified.json into session_dir."""
        marker_file = self.session_dir / "session_verified.json"
        try:
            marker_file.write_text(json.dumps({
                "portal": "Naukri",
                "connected": True,
                "verified_at": datetime.now(timezone.utc).isoformat(),
                "cookie_count": len(cookies),
                "verified_url": page.url,
                "connection_method": "mobile_headless_otp",
            }, indent=2), encoding="utf-8")
        except Exception as e:
            logger.debug(f"Notice saving session marker: {e}")


# Singleton engine instance
headless_auth_manager = HeadlessAuthManager()

