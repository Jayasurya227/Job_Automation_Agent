"""
Module: headless_auth.py
Purpose: Enterprise-grade Headless Authentication Engine for Mobile Portal Connection.
Standards: Supports silent background login with Playwright async stealth, automatic OTP detection,
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

from playwright.async_api import async_playwright, BrowserContext, Page, Playwright

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
from login_session import check_portal_login_sync

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
    timeout_sec: float = 300.0  # 5 minutes keep-alive for user to enter SMS/email OTP


class HeadlessAuthManager:
    """
    Manages headless browser instances for mobile portal login & OTP validation.
    Runs asynchronously on the native event loop to guarantee 100% stability
    across Windows asyncio environments without sync/async conflicts.
    """

    def __init__(self, session_dir: Optional[Path] = None, indeed_session_dir: Optional[Path] = None):
        self.session_dir = Path(session_dir or DEFAULT_SESSION_DIR)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.indeed_session_dir = Path(indeed_session_dir or (DATA_DIR / "indeed_session"))
        self.indeed_session_dir.mkdir(parents=True, exist_ok=True)
        self._active_sessions: Dict[str, PendingAuthSession] = {}

    async def cleanup_expired_sessions(self) -> None:
        """Closes and removes any abandoned login sessions older than timeout_sec."""
        now = time.time()
        expired_ids = [
            sid for sid, s in self._active_sessions.items()
            if now - s.created_at > s.timeout_sec
        ]
        for sid in expired_ids:
            logger.info(f"Closing expired headless auth session {sid}")
            await self.close_session(sid)

    async def close_session(self, session_id: str) -> None:
        """Safely closes Playwright context and frees resources asynchronously."""
        session = self._active_sessions.pop(session_id, None)
        if session:
            try:
                await session.context.close()
            except Exception as e:
                logger.debug(f"Notice closing context: {e}")
            try:
                await session.playwright.stop()
            except Exception as e:
                logger.debug(f"Notice stopping playwright: {e}")

    def _close_session(self, session_id: str) -> None:
        """Sync fallback helper for task/signal handlers."""
        session = self._active_sessions.pop(session_id, None)
        if session:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(session.context.close())
                    loop.create_task(session.playwright.stop())
                else:
                    loop.run_until_complete(session.context.close())
                    loop.run_until_complete(session.playwright.stop())
            except Exception:
                pass

    async def start_naukri_login(
        self,
        identifier: str,
        password: Optional[str] = None,
        use_otp_mode: bool = False,
        custom_session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Initiates headless Naukri login using Playwright async stealth.
        """
        await self.cleanup_expired_sessions()
        session_id = custom_session_id or str(uuid.uuid4())
        sanitize_session_preferences(self.session_dir)

        p = None
        context = None
        try:
            p = await async_playwright().start()
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
                    context = await p.chromium.launch_persistent_context(**kw)
                    break
                except Exception as e:
                    logger.debug(f"Could not launch channel={ch}: {e}")

            if not context:
                context = await p.chromium.launch_persistent_context(**launch_kwargs)

            await context.add_init_script(build_stealth_js())
            page = context.pages[0] if context.pages else await context.new_page()

            logger.info("Navigating to https://www.naukri.com/nlogin/login ...")
            await page.goto("https://www.naukri.com/nlogin/login", wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(2)

            cookies = await context.cookies()
            is_logged_in, _ = check_portal_login_sync("Naukri", page.url, cookies) if "nlogin" not in page.url else (False, "")
            if is_logged_in:
                self._save_session_marker(page, cookies, portal="Naukri")
                await context.close()
                await p.stop()
                return {
                    "status": "SUCCESS",
                    "message": "Already authenticated into Naukri candidate session.",
                    "portal": "naukri",
                }

            if password and not use_otp_mode:
                username_input = await page.query_selector("#usernameField, input[placeholder*='Username'], input[placeholder*='Email']")
                password_input = await page.query_selector("#passwordField, input[type='password']")
                submit_btn = await page.query_selector("button[type='submit'], .loginButton, button:has-text('Login')")

                if not username_input or not password_input or not submit_btn:
                    await context.close()
                    await p.stop()
                    return {"status": "ERROR", "message": "Naukri login fields could not be found."}

                await username_input.click()
                await asyncio.sleep(0.2)
                await username_input.fill("")
                for c in identifier:
                    await username_input.type(c, delay=random.uniform(25, 75))
                await asyncio.sleep(0.4)

                await password_input.click()
                await asyncio.sleep(0.2)
                await password_input.fill("")
                for c in password:
                    await password_input.type(c, delay=random.uniform(25, 75))
                await asyncio.sleep(0.5)

                await submit_btn.click()
                logger.info("Submitted login credentials, awaiting challenge / response...")

                for _ in range(10):
                    await asyncio.sleep(1)
                    curr_url = page.url.lower()

                    if "nlogin" not in curr_url and ("mnjuser" in curr_url or "mynaukri" in curr_url or "naukri.com" in curr_url):
                        cookies = await context.cookies()
                        auth_ok, reason = check_portal_login_sync("Naukri", page.url, cookies)
                        if auth_ok:
                            self._save_session_marker(page, cookies, portal="Naukri")
                            await context.close()
                            await p.stop()
                            return {
                                "status": "SUCCESS",
                                "message": "Successfully logged into Naukri candidate profile!",
                                "portal": "naukri",
                            }

                    err_el = await page.query_selector(".server-err, .err, .error-message, [class*='errorMessage']")
                    if err_el and await err_el.is_visible():
                        err_text = (await err_el.inner_text()).strip()
                        if err_text:
                            await context.close()
                            await p.stop()
                            return {"status": "ERROR", "message": f"Naukri Login Failed: {err_text}"}

                    otp_input = await page.query_selector(
                        "input[placeholder*='OTP'], input[name*='otp'], .otp-input, input[type='tel'][maxlength='6'], input[type='number'][maxlength='6']"
                    )
                    otp_screen_text = await page.query_selector("text='Enter OTP', text='Verification Code', text='OTP sent'")
                    if otp_input or otp_screen_text:
                        logger.info("OTP Challenge detected on Naukri!")
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

            if use_otp_mode or not password:
                otp_toggle = await page.query_selector("button:has-text('Use OTP'), .otp-link, span:has-text('Use OTP')")
                if otp_toggle:
                    await otp_toggle.click()
                    await asyncio.sleep(1.5)

                mobile_input = await page.query_selector("input[type='tel'], input[placeholder*='mobile'], #usernameField")
                get_otp_btn = await page.query_selector("button:has-text('Get OTP'), button[type='submit']")

                if mobile_input and get_otp_btn:
                    await mobile_input.click()
                    await mobile_input.fill("")
                    for c in identifier:
                        await mobile_input.type(c, delay=random.uniform(25, 75))
                    await asyncio.sleep(0.5)
                    await get_otp_btn.click()
                    logger.info(f"Requested OTP for {identifier}...")
                    await asyncio.sleep(2)

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
                    await context.close()
                except Exception:
                    pass
            if p:
                try:
                    await p.stop()
                except Exception:
                    pass
            return {"status": "ERROR", "message": f"Headless login error: {str(e)}"}

    async def verify_naukri_otp(self, session_id: str, otp: str) -> Dict[str, Any]:
        """Submits user OTP to active headless Naukri browser session."""
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
        try:
            logger.info(f"Entering OTP for session {session_id}...")
            otp_selectors = [
                "input[placeholder*='OTP']",
                "input[name*='otp']",
                "input.otp-input",
                "input[type='tel']",
                "input[type='number']",
                "input[maxlength='6']",
                "form input[type='text']",
            ]
            otp_input = None
            for sel in otp_selectors:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    otp_input = el
                    break

            digit_inputs = await page.query_selector_all(".otp-box input, input.digit-input, [class*='otp'] input")
            if len(digit_inputs) == 6 and len(clean_otp) == 6:
                for idx, digit in enumerate(clean_otp):
                    await digit_inputs[idx].click()
                    await digit_inputs[idx].fill(digit)
                    await asyncio.sleep(0.08)
            elif otp_input:
                await otp_input.click()
                await otp_input.fill("")
                for c in clean_otp:
                    await otp_input.type(c, delay=random.uniform(30, 80))
            else:
                await page.keyboard.type(clean_otp, delay=50)

            await asyncio.sleep(0.5)

            verify_btn_selectors = [
                "button:has-text('Verify')",
                "button:has-text('Submit')",
                "button:has-text('Login')",
                "button[type='submit']",
                ".submit-btn",
                ".verify-btn",
            ]
            for btn_sel in verify_btn_selectors:
                btn = await page.query_selector(btn_sel)
                if btn and await btn.is_visible():
                    await btn.click()
                    logger.info(f"Clicked OTP submit button ({btn_sel})")
                    break

            for _ in range(12):
                await asyncio.sleep(1)
                cookies = await context.cookies()
                auth_ok, auth_reason = check_portal_login_sync("Naukri", page.url, cookies)
                if auth_ok:
                    self._save_session_marker(page, cookies, portal="Naukri")
                    logger.info(f"✅ OTP Verified successfully for {session.identifier}!")
                    await self.close_session(session_id)
                    return {
                        "status": "SUCCESS",
                        "message": "Naukri account successfully connected and verified via Mobile OTP!",
                        "portal": "naukri",
                        "cookie_count": len(cookies),
                    }

                err_el = await page.query_selector(".server-err, .err, [class*='error'], text='Invalid OTP', text='Incorrect OTP'")
                if err_el and await err_el.is_visible():
                    err_msg = (await err_el.inner_text()).strip()
                    if err_msg and any(w in err_msg.lower() for w in ["otp", "invalid", "incorrect"]):
                        return {"status": "ERROR", "message": f"Verification failed: {err_msg}"}

            cookies = await context.cookies()
            auth_ok, auth_reason = check_portal_login_sync("Naukri", page.url, cookies)
            if auth_ok:
                self._save_session_marker(page, cookies, portal="Naukri")
                await self.close_session(session_id)
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

    async def start_indeed_login(
        self,
        identifier: str,
        password: Optional[str] = None,
        use_code_mode: bool = False,
        custom_session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Initiates headless Indeed login natively using Playwright async stealth.
        Supports both email/password (with potential 2FA code) and direct email/SMS login code.
        """
        await self.cleanup_expired_sessions()
        session_id = custom_session_id or str(uuid.uuid4())
        sanitize_session_preferences(self.indeed_session_dir)

        p = None
        context = None
        try:
            p = await async_playwright().start()
            launch_args = list(get_stealth_chromium_args())
            launch_args.extend(["--no-first-run", "--no-default-browser-check"])

            launch_kwargs = {
                "user_data_dir": str(self.indeed_session_dir),
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
                    context = await p.chromium.launch_persistent_context(**kw)
                    break
                except Exception as e:
                    logger.debug(f"Could not launch channel={ch}: {e}")

            if not context:
                context = await p.chromium.launch_persistent_context(**launch_kwargs)

            await context.add_init_script(build_stealth_js())
            page = context.pages[0] if context.pages else await context.new_page()

            logger.info("Navigating to https://secure.indeed.com/auth ...")
            try:
                await page.goto("https://secure.indeed.com/auth", wait_until="domcontentloaded", timeout=45000)
            except Exception as nav_e:
                logger.debug(f"Nav notice (trying in.indeed.com/account/login): {nav_e}")
                await page.goto("https://in.indeed.com/account/login", wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(2)

            cookies = await context.cookies()
            is_logged_in, _ = check_portal_login_sync("Indeed", page.url, cookies) if "/auth" not in page.url else (False, "")
            if is_logged_in:
                self._save_session_marker(page, cookies, portal="Indeed")
                await context.close()
                await p.stop()
                return {
                    "status": "SUCCESS",
                    "message": "Already authenticated into Indeed candidate session.",
                    "portal": "indeed",
                }

            email_selectors = [
                "input[name='__email']",
                "input[type='email']",
                "input#ifl-InputFormField-3",
                "input[name='identifier']",
                "input[id*='email']",
                "input[type='text']",
            ]
            identifier_input = None
            for sel in email_selectors:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    identifier_input = el
                    break

            if not identifier_input:
                sign_in_btn = await page.query_selector("a:has-text('Sign in'), button:has-text('Sign in')")
                if sign_in_btn:
                    await sign_in_btn.click()
                    await asyncio.sleep(2)
                    for sel in email_selectors:
                        el = await page.query_selector(sel)
                        if el and await el.is_visible():
                            identifier_input = el
                            break

            if not identifier_input:
                await context.close()
                await p.stop()
                return {"status": "ERROR", "message": "Could not locate Indeed login input field."}

            await identifier_input.click()
            await asyncio.sleep(0.2)
            await identifier_input.fill("")
            for c in identifier:
                await identifier_input.type(c, delay=random.uniform(25, 75))
            await asyncio.sleep(0.4)

            continue_selectors = [
                "button[type='submit']",
                "button:has-text('Continue')",
                "button:has-text('Next')",
                "button#login-submit-button",
            ]
            for csel in continue_selectors:
                cbtn = await page.query_selector(csel)
                if cbtn and await cbtn.is_visible():
                    await cbtn.click()
                    logger.info(f"Clicked Indeed Continue button ({csel})")
                    break

            await asyncio.sleep(2.5)

            password_input = await page.query_selector("input[type='password'], input[name='__password']")
            if password_input and password and not use_code_mode:
                logger.info("Entering Indeed password...")
                await password_input.click()
                await asyncio.sleep(0.2)
                await password_input.fill("")
                for c in password:
                    await password_input.type(c, delay=random.uniform(25, 75))
                await asyncio.sleep(0.4)

                submit_btn = await page.query_selector("button[type='submit'], button:has-text('Sign in'), button:has-text('Log in')")
                if submit_btn:
                    await submit_btn.click()
                await asyncio.sleep(2.5)

            elif use_code_mode or not password:
                code_opt = await page.query_selector(
                    "button:has-text('login code'), a:has-text('login code'), "
                    "button:has-text('Send a code'), a:has-text('Send a code'), "
                    "button:has-text('Email a code'), a:has-text('Email a code')"
                )
                if code_opt:
                    await code_opt.click()
                    await asyncio.sleep(2)

            for _ in range(6):
                curr_url = page.url.lower()
                cookies = await context.cookies()
                auth_ok, _ = check_portal_login_sync("Indeed", curr_url, cookies)
                if auth_ok:
                    self._save_session_marker(page, cookies, portal="Indeed")
                    await context.close()
                    await p.stop()
                    return {
                        "status": "SUCCESS",
                        "message": "Successfully logged into Indeed candidate profile!",
                        "portal": "indeed",
                    }
                await asyncio.sleep(1)

            err_el = await page.query_selector(".error-message, [class*='error'], [data-testid*='error']")
            if err_el and await err_el.is_visible():
                err_text = (await err_el.inner_text()).strip()
                if err_text and ("password" in err_text.lower() or "invalid" in err_text.lower() or "not recognized" in err_text.lower()):
                    await context.close()
                    await p.stop()
                    return {"status": "ERROR", "message": f"Indeed Login Failed: {err_text}"}

            logger.info("Indeed verification code prompt active. Keeping session alive for user code.")
            self._active_sessions[session_id] = PendingAuthSession(
                session_id=session_id,
                portal="indeed",
                identifier=identifier,
                playwright=p,
                context=context,
                page=page,
                created_at=time.time(),
            )
            return {
                "status": "OTP_REQUIRED",
                "session_id": session_id,
                "portal": "indeed",
                "message": f"Indeed verification code requested. Please enter the 6-digit code sent to {identifier}.",
            }

        except Exception as e:
            logger.error(f"Error starting headless Indeed login: {e}")
            if context:
                try:
                    await context.close()
                except Exception:
                    pass
            if p:
                try:
                    await p.stop()
                except Exception:
                    pass
            return {"status": "ERROR", "message": f"Indeed headless login error: {str(e)}"}

    async def verify_indeed_otp(self, session_id: str, otp: str) -> Dict[str, Any]:
        """Submits verification code to active headless Indeed browser session."""
        clean_code = otp.strip().replace(" ", "").replace("-", "")
        if not clean_code or len(clean_code) < 4:
            return {"status": "ERROR", "message": "Invalid code format. Please enter a valid verification code."}

        session = self._active_sessions.get(session_id)
        if not session:
            return {
                "status": "ERROR",
                "message": "Login session expired or not found. Please click Connect to request a fresh code.",
            }

        page = session.page
        context = session.context
        try:
            logger.info(f"Entering Indeed verification code for session {session_id}...")
            code_selectors = [
                "input[data-testid='verification-code-input']",
                "input[name='verificationCode']",
                "input#code",
                "input[placeholder*='code']",
                "input[placeholder*='OTP']",
                "input[type='tel']",
                "input[type='number']",
                "input[maxlength='6']",
                "input[type='text']",
            ]
            code_input = None
            for sel in code_selectors:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    code_input = el
                    break

            digit_inputs = await page.query_selector_all("input[data-testid*='otp-input'], [class*='code-box'] input, [class*='digit'] input")
            if len(digit_inputs) == 6 and len(clean_code) == 6:
                for idx, digit in enumerate(clean_code):
                    await digit_inputs[idx].click()
                    await digit_inputs[idx].fill(digit)
                    await asyncio.sleep(0.08)
            elif code_input:
                await code_input.click()
                await code_input.fill("")
                for c in clean_code:
                    await code_input.type(c, delay=random.uniform(30, 80))
            else:
                await page.keyboard.type(clean_code, delay=50)

            await asyncio.sleep(0.5)

            verify_btn_selectors = [
                "button[type='submit']",
                "button:has-text('Verify')",
                "button:has-text('Sign in')",
                "button:has-text('Continue')",
                "button:has-text('Submit')",
            ]
            for btn_sel in verify_btn_selectors:
                btn = await page.query_selector(btn_sel)
                if btn and await btn.is_visible():
                    await btn.click()
                    logger.info(f"Clicked Indeed code submit button ({btn_sel})")
                    break

            for _ in range(12):
                await asyncio.sleep(1)
                cookies = await context.cookies()
                auth_ok, auth_reason = check_portal_login_sync("Indeed", page.url, cookies)
                if auth_ok:
                    self._save_session_marker(page, cookies, portal="Indeed")
                    logger.info(f"✅ Indeed code verified successfully for {session.identifier}!")
                    await self.close_session(session_id)
                    return {
                        "status": "SUCCESS",
                        "message": "Indeed account successfully connected and verified via Mobile Code!",
                        "portal": "indeed",
                        "cookie_count": len(cookies),
                    }

                err_el = await page.query_selector(".error-message, [class*='error'], text='Invalid code', text='Incorrect code', text='Code expired'")
                if err_el and await err_el.is_visible():
                    err_msg = (await err_el.inner_text()).strip()
                    if err_msg and any(w in err_msg.lower() for w in ["code", "invalid", "incorrect", "expired"]):
                        return {"status": "ERROR", "message": f"Verification failed: {err_msg}"}

            cookies = await context.cookies()
            auth_ok, auth_reason = check_portal_login_sync("Indeed", page.url, cookies)
            if auth_ok:
                self._save_session_marker(page, cookies, portal="Indeed")
                await self.close_session(session_id)
                return {
                    "status": "SUCCESS",
                    "message": "Indeed account successfully connected!",
                    "portal": "indeed",
                    "cookie_count": len(cookies),
                }

            return {
                "status": "ERROR",
                "message": f"Indeed verification timed out. (Status: {auth_reason})",
            }

        except Exception as e:
            logger.error(f"Error during Indeed code verification: {e}")
            return {"status": "ERROR", "message": f"Verification error: {str(e)}"}

    def _save_session_marker(self, page: Page, cookies: list[dict], portal: str = "Naukri") -> None:
        """Saves session_verified.json into respective session_dir."""
        target_dir = self.indeed_session_dir if portal.lower() == "indeed" else self.session_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        marker_file = target_dir / "session_verified.json"
        try:
            marker_file.write_text(json.dumps({
                "portal": portal,
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
