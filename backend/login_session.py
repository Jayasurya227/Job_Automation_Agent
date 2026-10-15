"""
Interactive Browser Session Login Utility.
Allows candidates to log into LinkedIn, Indeed, or Naukri once in a headed browser.
Session cookies and authentication tokens are permanently saved to backend/data/browser_session/
so the autonomous agent never asks for passwords or triggers 2FA in code.
"""

import sys
import asyncio
from pathlib import Path

# Safe Windows stdout encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agent.browser import BrowserSessionManager, DEFAULT_SESSION_DIR

PORTALS = {
    "1": ("Naukri", "https://www.naukri.com/nlogin/login"),
    "2": ("Google / General Portal", "https://accounts.google.com/"),
}


async def run_interactive_session(target_url: str, portal_name: str):
    """Launches a visible Chromium browser with persistent session for manual login."""
    print("=" * 70)
    print(f"🚀 LAUNCHING HEADED BROWSER FOR: {portal_name.upper()}")
    print("=" * 70)
    print(f"📁 Session Storage Path: {DEFAULT_SESSION_DIR}")
    print("💡 INSTRUCTIONS:")
    print("   1. A real Chrome window will open.")
    print("   2. Log into your account normally and complete any 2FA/OTP prompts.")
    print("   3. Once you see your feed or profile page, come back to this terminal.")
    print("   4. Press [ENTER] to safely close the browser and save your cookies permanently.")
    print("=" * 70)

    manager = BrowserSessionManager(headless=False)

    async with manager.get_context(headless=False) as context:
        page = await context.new_page()
        print(f"🌐 Navigating to {target_url} ...")
        await page.goto(target_url, wait_until="domcontentloaded")

        # Wait for user confirmation in terminal
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, input, "\n👉 Press [ENTER] once you have logged in and verified your account...")

        print("💾 Saving persistent session state and cookies...")
        cookies = await context.cookies()
        print(f"✅ Successfully captured {len(cookies)} cookies across current domains.")

    print("\n🎉 BROWSER CLOSED CLEANLY. Session saved permanently!")
    print(f"Autonomous agent can now access {portal_name} using this saved session.")


def main():
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
