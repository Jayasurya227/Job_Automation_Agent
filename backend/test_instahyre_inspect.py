"""
Test script to inspect Instahyre candidate opportunities page structure.
Uses the verified session in backend/data/instahyre_session.
"""
import sys
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agent.stealth import get_stealth_chromium_args, build_stealth_js, get_random_fingerprint

session_path = Path("backend/data/instahyre_session").resolve()

def inspect_instahyre():
    print(f"Opening Instahyre with session at: {session_path}")
    api_responses = []

    launch_args = list(get_stealth_chromium_args())
    fingerprint = get_random_fingerprint()

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=str(session_path),
            channel="chrome",
            headless=True,
            args=launch_args,
            user_agent=fingerprint["user_agent"],
            locale="en-US",
            timezone_id="Asia/Kolkata",
            viewport={"width": 1280, "height": 800},
        )

        browser.add_init_script(build_stealth_js())
        page = browser.pages[0] if browser.pages else browser.new_page()

        # Listen for internal API calls
        def handle_response(response):
            if "api" in response.url or "opportunities" in response.url:
                ct = response.headers.get("content-type", "")
                if "json" in ct:
                    try:
                        data = response.json()
                        api_responses.append({"url": response.url, "keys": list(data.keys()) if isinstance(data, dict) else len(data)})
                    except Exception:
                        pass

        page.on("response", handle_response)

        print("Navigating to https://www.instahyre.com/candidate/opportunities ...")
        page.goto("https://www.instahyre.com/candidate/opportunities", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(8000)

        print(f"Current URL: {page.url}")
        print(f"Page Title: {page.title()}")

        # Check for job opportunity elements
        selectors_to_check = [
            ".opportunity-card",
            ".job-card",
            "#opportunities",
            "[data-opportunity-id]",
            ".opportunity",
            ".job",
            ".employer-row",
            ".cursor-pointer",
            "div[class*='opportunity']",
            "div[class*='job']"
        ]

        print("\nChecking candidate DOM elements:")
        for sel in selectors_to_check:
            count = page.locator(sel).count()
            if count > 0:
                print(f"  Found {count} elements for selector: '{sel}'")

        # Dump some sample text content
        body_text = page.inner_text("body")
        print(f"\nBody preview (first 500 chars):\n{body_text[:500]}")

        print(f"\nCaptured {len(api_responses)} JSON API responses:")
        for r in api_responses[:5]:
            print(" ", r)

        browser.close()

if __name__ == "__main__":
    inspect_instahyre()
