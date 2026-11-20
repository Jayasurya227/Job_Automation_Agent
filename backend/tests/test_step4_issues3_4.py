import sys
import os
import asyncio
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

# Force WindowsSelectorEventLoopPolicy to prevent IOCP hang on Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.db.session import SessionLocal
from app.db.models import User, Job
from app.agent.booster import (
    boost_naukri_profile,
    _user_booster_locks,
    _last_boost_timestamps,
    BOOSTER_COOLDOWN_SECONDS,
)

def run_tests():
    print("==================================================================")
    print("STEP 4 (Issues 4.3 & 4.4 - Bugs 21 & 22): BROWSER BOOSTER ISOLATION")
    print("==================================================================")

    db = SessionLocal()
    try:
        u1 = db.query(User).filter(User.id == 1).first()
        u2 = db.query(User).filter(User.id == 2).first()
        assert u1 is not None and u2 is not None
        u1_initial_jobs = db.query(Job).filter(Job.user_id == 1).count()
        print(f"Pre-flight: User 1 ({u1.email}) has {u1_initial_jobs} jobs. User 2 ({u2.email}) exists.")

        # -------------------------------------------------------------
        # TEST 1: Browser Fallback Mechanism (Chrome -> Chromium fallback)
        # -------------------------------------------------------------
        print("\n--- Test 1: Chrome -> Chromium Fallback Engine (Bug 21) ---")
        attempted_channels = []

        def mock_launch_persistent_context(**kwargs):
            ch = kwargs.get("channel")
            attempted_channels.append(ch)
            if ch == "chrome":
                raise RuntimeError("Executable doesn't exist at C:\\Program Files\\Google\\Chrome\\chrome.exe")
            # Successful fallback to Chromium (channel=None)
            mock_context = MagicMock()
            mock_page = MagicMock()
            mock_file_input = MagicMock()
            mock_page.query_selector.return_value = mock_file_input
            mock_context.pages = [mock_page]
            return mock_context

        # Mock verified session & resume for User 1
        with patch("pathlib.Path.exists", return_value=True), \
             patch("app.core.user_storage.get_user_resume", return_value=Path("test_resume.pdf")), \
             patch("app.agent.booster.sync_playwright") as mock_pw:

            mock_pw_instance = MagicMock()
            mock_pw.return_value.__enter__.return_value = mock_pw_instance
            mock_pw_instance.chromium.launch_persistent_context.side_effect = mock_launch_persistent_context

            # Reset last boost for clean test
            _last_boost_timestamps[1] = 0.0
            res = boost_naukri_profile(user_id=1, bypass_cooldown=True)

            assert "chrome" in attempted_channels, "Must attempt chrome channel first"
            assert None in attempted_channels, "Must fallback to None (Chromium) when chrome fails"
            assert res["status"] == "success", f"Expected success with fallback, got: {res}"
        print(f"  [PASS] Playwright gracefully fell back from 'chrome' to bundled Chromium: {attempted_channels}")

        # -------------------------------------------------------------
        # TEST 2: Multi-User Locking & Concurrency Protection (Bug 22)
        # -------------------------------------------------------------
        print("\n--- Test 2: Multi-User Booster Concurrency & Locks (Bug 22) ---")
        lock1 = _user_booster_locks[1]
        lock2 = _user_booster_locks[2]
        assert lock1 is not lock2, "Locks for User 1 and User 2 must be completely independent"

        # Acquire lock1 manually (simulating active booster for User 1)
        acquired = lock1.acquire(blocking=False)
        assert acquired, "Lock 1 must be acquired"

        # Calling boost_naukri_profile for User 1 while locked returns 'already_running'
        res_conflict = boost_naukri_profile(user_id=1, bypass_cooldown=True)
        assert res_conflict["status"] == "already_running"
        print(f"  [PASS] User 1 re-entrant boost cleanly rejected: '{res_conflict['message']}'")

        # Calling boost_naukri_profile for User 2 is NOT blocked by User 1's lock
        with patch("pathlib.Path.exists", return_value=False):
            # Returns session not found for User 2 (not 'already_running')
            res_u2 = boost_naukri_profile(user_id=2, bypass_cooldown=True)
            assert res_u2["status"] != "already_running", "User 2 must not be blocked by User 1's lock"
        print("  [PASS] User 1 and User 2 locks are completely isolated.")

        lock1.release()

        # -------------------------------------------------------------
        # TEST 3: Cooldown / Rate Limiting (Bug 22)
        # -------------------------------------------------------------
        print("\n--- Test 3: Booster Cooldown / Rate Limiting ---")
        _last_boost_timestamps[1] = time.time() - 30  # boosted 30 seconds ago
        res_cooldown = boost_naukri_profile(user_id=1, bypass_cooldown=False)
        assert res_cooldown["status"] == "already_boosted"
        assert "recently" in res_cooldown["message"]
        print(f"  [PASS] Rapid booster trigger debounced with status: '{res_cooldown['status']}'")

        # -------------------------------------------------------------
        # TEST 4: User 1 Zero Data Loss Verification
        # -------------------------------------------------------------
        print("\n--- Test 4: User 1 Zero Data Loss Verification ---")
        u1_final_jobs = db.query(Job).filter(Job.user_id == 1).count()
        assert u1_final_jobs == u1_initial_jobs, f"User 1 jobs altered from {u1_initial_jobs} to {u1_final_jobs}!"
        print(f"  [PASS] User 1 jobs intact: exactly {u1_final_jobs} jobs.")

        print("\n==================================================================")
        print("ALL 4 CHECKS PASSED FOR STEP 4 (ISSUES 4.3 & 4.4)!")
        print("==================================================================")

    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
