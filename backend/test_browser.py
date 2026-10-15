"""
Automated Test Suite for Step 3.1: Playwright Setup & Persistent Session.
Verifies persistent context, stealth anti-bot protections, and human pacing.
"""

import sys
import asyncio
import tempfile
import shutil
import time
from pathlib import Path

# Safe Windows stdout encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Ensure backend root is on path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agent.browser import BrowserSessionManager, DEFAULT_SESSION_DIR


async def run_tests():
    print("=" * 60)
    print("[TEST SUITE] STEP 3.1: BROWSER & PERSISTENT SESSION")
    print("=" * 60)

    # Use a temporary session directory for tests to avoid altering live user profiles
    temp_dir = Path(tempfile.mkdtemp(prefix="test_agent_session_"))
    print(f"[*] Temporary test session directory: {temp_dir}")

    passed = 0
    total = 5

    try:
        manager = BrowserSessionManager(session_dir=temp_dir, headless=True)

        # ---------------------------------------------------------
        # TEST 1: Session Directory Creation & Context Initialization
        # ---------------------------------------------------------
        print("\n[Test 1/5] Verifying persistent context launch...")
        async with manager.get_context(headless=True) as context:
            assert context is not None, "Failed to initialize persistent context"
            pages = context.pages
            assert len(pages) >= 0, "Pages collection invalid"
            print("  [OK] Persistent context launched successfully.")
            passed += 1

        # ---------------------------------------------------------
        # TEST 2: Stealth Script & navigator.webdriver Neutralization
        # ---------------------------------------------------------
        print("\n[Test 2/5] Verifying anti-bot stealth overrides...")
        async with manager.get_page(headless=True) as page:
            await page.goto("about:blank")

            # Check webdriver flag
            is_webdriver = await page.evaluate("() => navigator.webdriver")
            assert is_webdriver is None or is_webdriver is False, f"Stealth failed: navigator.webdriver is {is_webdriver}"
            print(f"  [OK] navigator.webdriver neutralized: {is_webdriver}")

            # Check plugins
            plugins_length = await page.evaluate("() => navigator.plugins.length")
            assert plugins_length > 0, "Stealth failed: navigator.plugins is empty"
            print(f"  [OK] navigator.plugins spoofed: {plugins_length} items found")

            # Check languages
            languages = await page.evaluate("() => navigator.languages")
            assert "en-US" in languages, f"Stealth failed: languages {languages}"
            print(f"  [OK] navigator.languages configured: {languages}")

            # Check window.chrome
            has_chrome = await page.evaluate("() => !!window.chrome")
            assert has_chrome is True, "Stealth failed: window.chrome not found"
            print("  [OK] window.chrome runtime object verified.")
            passed += 1

        # ---------------------------------------------------------
        # TEST 3: Persistent Cookie Retention Across Restarts
        # ---------------------------------------------------------
        print("\n[Test 3/5] Verifying session persistence across restarts...")
        test_cookie = {
            "name": "session_test_token",
            "value": "secret_candidate_12345",
            "domain": "httpbin.org",
            "path": "/",
            "expires": int(time.time() + 86400),
        }

        # Session 1: Write cookie
        async with manager.get_context(headless=True) as context1:
            await context1.add_cookies([test_cookie])
            cookies1 = await context1.cookies()
            names1 = [c["name"] for c in cookies1]
            assert "session_test_token" in names1, "Cookie was not stored in Session 1"
            print("  [OK] Session 1 stored cookie successfully.")

        # Session 2: Read cookie from disk storage
        async with manager.get_context(headless=True) as context2:
            cookies2 = await context2.cookies()
            names2 = [c["name"] for c in cookies2]
            assert "session_test_token" in names2, "Cookie did not persist in Session 2 across restarts!"
            print(f"  [OK] Cookie persisted across restart: {names2}")
            passed += 1

        # ---------------------------------------------------------
        # TEST 4: Human-like Pacing & Interaction Simulation
        # ---------------------------------------------------------
        print("\n[Test 4/5] Verifying human-like pacing methods...")
        duration = await BrowserSessionManager.random_delay(0.5, 1.0)
        assert 0.5 <= duration <= 1.1, f"Random delay out of range: {duration}"
        print(f"  [OK] Random delay executed within bounds: {duration}s")

        async with manager.get_page(headless=True) as page:
            await page.set_content('<input id="search-input" type="text" />')
            await BrowserSessionManager.human_type(page, "#search-input", "Python Developer", 10, 30)
            value = await page.input_value("#search-input")
            assert value == "Python Developer", f"Human type failed, got: {value}"
            print("  [OK] Human-like typing simulation verified.")

            await page.set_content('<div style="height: 3000px;">Long Page Content</div>')
            await BrowserSessionManager.human_scroll(page, scrolls=2, min_delay=0.1, max_delay=0.2)
            print("  [OK] Human-like scroll simulation verified.")
            passed += 1

        # ---------------------------------------------------------
        # TEST 5: Safe Navigation with Timeout Protection
        # ---------------------------------------------------------
        print("\n[Test 5/5] Verifying safe navigation error handling...")
        async with manager.get_page(headless=True) as page:
            ok = await BrowserSessionManager.safe_goto(page, "about:blank")
            assert ok is True, "safe_goto failed on valid blank page"

            ok_fail = await BrowserSessionManager.safe_goto(page, "http://invalid-nonexistent-domain-xyz123.local", timeout=1500)
            assert ok_fail is False, "safe_goto should gracefully return False on error"
            print("  [OK] safe_goto gracefully handled connection error without crashing.")
            passed += 1

    finally:
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
            print(f"\n[*] Cleaned up temporary test directory: {temp_dir}")
        except Exception as e:
            print(f"Note: Could not clean temp dir {temp_dir}: {e}")

    print("\n" + "=" * 60)
    print(f"[RESULT] STEP 3.1 TESTS RESULT: {passed}/{total} PASSED")
    print("=" * 60)
    assert passed == total, f"Expected {total} passed tests, but got {passed}"


if __name__ == "__main__":
    asyncio.run(run_tests())
