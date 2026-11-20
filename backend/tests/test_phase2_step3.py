"""
Phase 2 - Step 3 Rigorous Verification Test
Enterprise Verification Suite:
1. Verifies per-user Naukri browser session directory isolation (User 1 vs User 2).
2. Verifies GET /api/portals/naukri/session-status returns independent, accurate status per user without leaks.
3. Verifies HeadlessAuthManager session marker writes exclusively to the target user's browser vault.
4. Verifies User 1's session files remain 100% untouched when User 2 connects.
5. Verifies multi-user security ownership guard: User 2 cannot verify or hijack User 1's OTP session.
6. Verifies Naukri booster directory resolution scopes strictly per user.
"""

import sys
import json
import time
from pathlib import Path
from unittest.mock import MagicMock

# Set up paths
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.user_storage import (
    get_user_browser_session_dir,
    get_user_base_dir,
    ensure_user_storage,
)
from app.agent.headless_auth import (
    headless_auth_manager,
    PendingAuthSession,
)
from app.agent.booster import boost_naukri_profile
from main import get_naukri_session_status
from app.db.models import User


def run_tests():
    print("=" * 70)
    print("🧪 PHASE 2 STEP 3: RIGOROUS BROWSER SESSION ISOLATION TEST SUITE")
    print("=" * 70)

    # 1. Directory Structure Isolation
    print("\n[Test 1] Verifying per-user browser session path resolution...")
    u1_session = get_user_browser_session_dir(1)
    u2_session = get_user_browser_session_dir(2)

    assert u1_session != u2_session, "User 1 and User 2 session directories must NOT collide!"
    assert u1_session == backend_dir / "data" / "users" / "1" / "browser_session"
    assert u2_session == backend_dir / "data" / "users" / "2" / "browser_session"
    assert u1_session.exists(), "User 1 session directory should exist from Step 1 migration."
    print(f"  ✅ User 1 Session Path: {u1_session}")
    print(f"  ✅ User 2 Session Path: {u2_session}")

    # Ensure User 2 has clean directory
    ensure_user_storage(2)
    u2_marker = u2_session / "session_verified.json"
    if u2_marker.exists():
        u2_marker.unlink()

    # 2. Status Endpoint Scoping
    print("\n[Test 2] Testing /api/portals/naukri/session-status per-user scoping...")
    user1_mock = User(id=1, email="candidate1@autojob.ai", full_name="Candidate 1")
    user2_mock = User(id=2, email="candidate2@autojob.ai", full_name="Candidate 2")

    u1_status = get_naukri_session_status(current_user=user1_mock)
    u2_status = get_naukri_session_status(current_user=user2_mock)

    print(f"  User 1 status: connected={u1_status['connected']}, status={u1_status['status']}")
    print(f"  User 2 status: connected={u2_status['connected']}, status={u2_status['status']}")

    assert u1_status["user_id"] == 1
    assert u2_status["user_id"] == 2
    assert u2_status["connected"] is False, "User 2 must NOT inherit User 1's connected state!"
    assert u2_status["status"] == "unconfigured", f"Expected unconfigured for User 2, got {u2_status['status']}"
    assert u1_status["session_dir"] != u2_status["session_dir"], "Status endpoints must reference distinct session directories"
    print("  ✅ Session status is 100% isolated per user!")

    # 3. Session Marker Write Isolation
    print("\n[Test 3] Verifying session marker writing strictly to User 2 directory...")
    # Capture User 1's session files state
    u1_files_before = set(p.name for p in u1_session.iterdir()) if u1_session.exists() else set()
    u1_marker = u1_session / "session_verified.json"
    u1_marker_content_before = u1_marker.read_text(encoding="utf-8") if u1_marker.exists() else ""

    # Mock Playwright Page
    mock_page = MagicMock()
    mock_page.url = "https://www.naukri.com/mnjuser/homepage"
    mock_cookies = [{"name": "nauk_user", "value": "test_u2_token"}]

    headless_auth_manager._save_session_marker(
        page=mock_page,
        cookies=mock_cookies,
        portal="Naukri",
        target_dir=u2_session,
    )

    assert u2_marker.exists(), "User 2 session_verified.json was not created!"
    u2_data = json.loads(u2_marker.read_text(encoding="utf-8"))
    assert u2_data["portal"] == "Naukri"
    assert u2_data["connected"] is True
    assert u2_data["cookie_count"] == 1
    print("  ✅ User 2 session_verified.json correctly saved in users/2/browser_session/")

    # Verify User 1 remained completely untouched
    u1_marker_content_after = u1_marker.read_text(encoding="utf-8") if u1_marker.exists() else ""
    assert u1_marker_content_before == u1_marker_content_after, "CRITICAL: User 1 marker was altered by User 2 action!"
    u1_files_after = set(p.name for p in u1_session.iterdir()) if u1_session.exists() else set()
    assert u1_files_before == u1_files_after, "CRITICAL: User 1 file listing changed during User 2 login!"
    print("  ✅ User 1 files verified 100% UNTOUCHED and intact.")

    # Now verify User 2's session-status endpoint immediately reflects User 2's connection
    u2_status_after = get_naukri_session_status(current_user=user2_mock)
    assert u2_status_after["connected"] is True, "User 2 should now show connected=True!"
    assert u2_status_after["status"] == "connected"
    print("  ✅ User 2 session status immediately detects User 2's active session!")

    # 4. Multi-Tenant Session Security (Anti-Hijacking / Anti-Collision)
    print("\n[Test 4] Verifying cross-user OTP submission security check...")
    test_session_id = "test-sec-session-u1"
    headless_auth_manager._active_sessions[test_session_id] = PendingAuthSession(
        session_id=test_session_id,
        portal="naukri",
        identifier="9876543210",
        playwright=MagicMock(),
        context=MagicMock(),
        page=MagicMock(),
        created_at=time.time(),
        user_id=1,
        session_dir=u1_session,
    )

    # Attempt 1: User 2 attempts to verify User 1's session
    coro = headless_auth_manager.verify_naukri_otp(
        session_id=test_session_id,
        otp="123456",
        expected_user_id=2,  # User 2 calling
    )
    try:
        coro.send(None)
        hijack_attempt = None
    except StopIteration as e:
        hijack_attempt = e.value
    assert hijack_attempt["status"] == "ERROR", f"Expected error for cross-user hijack, got {hijack_attempt}"
    assert "Access denied" in hijack_attempt["message"], f"Expected 'Access denied', got {hijack_attempt['message']}"
    print(f"  ✅ Anti-Hijacking Check Succeeded: {hijack_attempt['message']}")

    # Clean up test session
    headless_auth_manager._active_sessions.pop(test_session_id, None)

    # 5. Profile Booster Directory Scoping
    print("\n[Test 5] Verifying profile booster scopes strictly per user...")
    non_existent_user_id = 999999
    res = boost_naukri_profile(user_id=non_existent_user_id)
    assert res["status"] == "error"
    assert f"User {non_existent_user_id}" in res["message"]
    print(f"  ✅ Booster safely rejected unconfigured User {non_existent_user_id}: {res['message']}")

    # Clean up temporary User 2 test marker so we leave clean state
    if u2_marker.exists():
        u2_marker.unlink()
        print("  🧹 Cleaned up temporary test marker for User 2.")

    print("\n" + "=" * 70)
    print("🎉 ALL PHASE 2 STEP 3 TESTS PASSED WITH 100% ACCURACY & SECURITY!")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()
