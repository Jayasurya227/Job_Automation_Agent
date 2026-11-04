"""
Interactive Browser Session Login Utility.
Allows candidates to log into LinkedIn, Indeed, or Naukri once in a headed browser.
Session cookies and authentication tokens are permanently saved to backend/data/browser_session/
so the autonomous agent never asks for passwords or triggers 2FA in code.
"""

import os
import sys
import asyncio
import subprocess
from pathlib import Path
from typing import Optional

# Safe Windows stdout encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agent.browser import BrowserSessionManager, DEFAULT_SESSION_DIR, sanitize_session_preferences

PORTALS = {
    "1": ("Naukri", "https://www.naukri.com/nlogin/login"),
    "2": ("Indeed", "https://in.indeed.com/"),
    "3": ("Google / General Portal", "https://accounts.google.com/"),
}


async def verify_portal_login(portal_name: str, page, cookies: list[dict]) -> tuple[bool, str]:
    """
    Strictly verifies whether the user is genuinely logged into their candidate account.
    Prevents false-positive green marks caused by anonymous guest cookies.
    """
    current_url = page.url.lower()
    cookie_dict = {c.get("name", "").lower(): c.get("value", "") for c in cookies}
    cookie_names = set(cookie_dict.keys())

    p = portal_name.lower()
    if "naukri" in p:
        if "nlogin" in current_url:
            return False, f"Browser is still on the Naukri login page ({page.url})."
        is_naukri_user = any(k in cookie_names for k in ["nauk_user", "user_id", "auth_token"]) or "mnjuser" in current_url
        if is_naukri_user:
            return True, "Naukri candidate profile session verified."
        return False, "No active Naukri candidate session detected."

    elif "indeed" in p:
        has_indeed_auth = any(k in cookie_names for k in ["shoe", "surf", "indeed_rno", "surfc"])
        if has_indeed_auth and "auth" not in current_url:
            return True, "Indeed authenticated session verified."
        return False, "No active Indeed account login detected."

    # General portal fallback
    if "/login" not in current_url and len(cookies) >= 5:
        return True, "Session cookies captured."
    return False, "Authentication not detected."


async def run_interactive_session(target_url: str, portal_name: str, session_dir: Optional[Path] = None):
    """
    Launches a visible Chromium browser with persistent session for manual login.
    Uses the exact same BrowserSessionManager engine that worked for Naukri & Indeed.
    """
    storage_path = Path(session_dir or DEFAULT_SESSION_DIR)
    storage_path.mkdir(parents=True, exist_ok=True)

    # Sanitize any saved negative/off-screen window coordinates before launching
    sanitize_session_preferences(storage_path)

    print("=" * 70)
    print(f"🚀 LAUNCHING HEADED BROWSER FOR: {portal_name.upper()}")
    print("=" * 70)
    print(f"📁 Session Storage Path: {storage_path}")
    print("💡 INSTRUCTIONS:")
    print("   1. Real Google Chrome is opening directly on your desktop screen.")
    print("   2. Log into your account normally and complete any 2FA/OTP prompts.")
    print("   3. Once you see your profile or dashboard, return to this terminal.")
    print("   4. ⚠️ DO NOT close the Chrome window with the red [X] button.")
    print("   5. Press [ENTER] in this terminal first, and it will save and close cleanly.")
    print("=" * 70)

    manager = BrowserSessionManager(session_dir=storage_path, headless=False)

    async with manager.get_context(headless=False) as context:
        page = await context.new_page()

        print(f"🌐 Navigating to {target_url} ...")
        try:
            await page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
        except Exception as nav_err:
            print(f"ℹ️ Browser navigation notice: {nav_err}")

        loop = asyncio.get_event_loop()
        marker_file = storage_path / "session_verified.json"

        # Retry loop: a failed check no longer ends the session. You can finish logging in and press ENTER again.
        while True:
            answer = await loop.run_in_executor(
                None, input,
                "\n👉 Press [ENTER] once you have logged in in Chrome (do not close window). Type q + ENTER to quit without saving: "
            )
            if answer.strip().lower() == "q":
                print("Quit without saving. No session was stored.")
                return

            print("\n🔍 Verifying candidate account authentication...")
            try:
                cookies = await context.cookies()
                page_ref = page
            except Exception:
                print("\n" + "!" * 70)
                print("❌ LOGIN VERIFICATION FAILED!")
                print("Reason: The browser window was closed before verification.")
                print("!" * 70)
                return

            is_authenticated, auth_reason = await verify_portal_login(portal_name, page_ref, cookies)
            if is_authenticated:
                break

            print("\n" + "!" * 70)
            print("❌ NOT VERIFIED YET")
            print(f"Reason: {auth_reason}")
            print("⚠️  Session NOT saved. Finish logging in, then press ENTER again (or q to quit).")
            print("!" * 70)

        print("\n" + "=" * 70)
        print(f"✅ AUTHENTICATION VERIFIED: {auth_reason}")
        print(f"💾 Saving persistent session state and {len(cookies)} cookies...")
        print("=" * 70)

        import json
        from datetime import datetime, timezone
        try:
            marker_file.write_text(json.dumps({
                "portal": portal_name,
                "connected": True,
                "verified_at": datetime.now(timezone.utc).isoformat(),
                "cookie_count": len(cookies),
                "verified_url": page.url
            }, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"Notice writing session marker: {e}")

    print(f"\n🎉 BROWSER CLOSED CLEANLY. {portal_name.upper()} session saved permanently!")
    print(f"Autonomous agent can now access {portal_name} using this verified session.")


def main():
    if len(sys.argv) > 1 and sys.argv[1].lower() in ["naukri", "--naukri", "-n"]:
        print("Starting direct Naukri login session...")
        asyncio.run(run_interactive_session("https://www.naukri.com/nlogin/login", "Naukri"))
        return

    if len(sys.argv) > 1 and sys.argv[1].lower() in ["indeed", "--indeed", "-i"]:
        print("Starting direct Indeed login session...")
        from app.config import DATA_DIR
        indeed_dir = DATA_DIR / "indeed_session"
        asyncio.run(run_interactive_session("https://in.indeed.com/", "Indeed", session_dir=indeed_dir))
        return

    print("\n" + "=" * 50)
    print("🔑 AUTONOMOUS AGENT: SESSION INITIALIZER")
    print("=" * 50)
    print("Select the portal you wish to log into:")
    for key, (name, url) in PORTALS.items():
        print(f"  [{key}] {name} ({url})")
    print("  [5] Custom URL")
    print("  [Q] Exit")

    choice = input("\nEnter choice (1-5 or Q): ").strip()

    if choice.upper() == "Q":
        print("Cancelled.")
        return

    if choice in PORTALS:
        name, url = PORTALS[choice]
    elif choice == "5":
        url = input("Enter custom login URL: ").strip()
        name = "Custom Portal"
    else:
        print("Invalid choice.")
        return

    asyncio.run(run_interactive_session(url, name))


if __name__ == "__main__":
    main()
