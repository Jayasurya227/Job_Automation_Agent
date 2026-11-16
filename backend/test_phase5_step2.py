"""
Test Suite: Phase 5 - Step 2 Verification
Focus: Dual Naukri Portal Session Isolation, Anti-Hijacking Guard, and Zero Cross-Contamination
Architectural Standard: 20-30 Years Principal Architect Rigor
"""
import sys
import asyncio
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import json
from pathlib import Path
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from main import app
from app.core.security import create_access_token
from app.core.user_storage import get_user_browser_session_dir
from app.agent.headless_auth import headless_auth_manager, PendingAuthSession
from app.db.session import SessionLocal
from app.db.models import User
from app.core.security import hash_password

def ensure_test_user_2():
    db = SessionLocal()
    try:
        u2 = db.query(User).filter(User.id == 2).first()
        if not u2:
            u2 = User(
                id=2,
                email="candidate2@autojob.ai",
                password_hash=hash_password("TestPassword123!"),
                full_name="Candidate Two",
                is_active=True
            )
            db.add(u2)
            db.commit()
    finally:
        db.close()

ensure_test_user_2()
client = TestClient(app)

TOKEN_U1 = create_access_token(user_id=1, email="rayavaramjayasurya@gmail.com")
TOKEN_U2 = create_access_token(user_id=2, email="candidate2@autojob.ai")
HEADERS_U1 = {"Authorization": f"Bearer {TOKEN_U1}"}
HEADERS_U2 = {"Authorization": f"Bearer {TOKEN_U2}"}

def test_session_directory_vault_isolation():
    print("Testing Naukri Browser Session Vault Directory Isolation...")
    dir1 = get_user_browser_session_dir(1)
    dir2 = get_user_browser_session_dir(2)

    assert dir1.exists(), "User 1 browser session directory must exist"
    assert dir2.exists(), "User 2 browser session directory must exist"
    assert dir1 != dir2, "User 1 and User 2 session directories must be distinct paths"
    assert str(dir1).endswith(str(Path("data/users/1/browser_session"))), f"Path mismatch for User 1: {dir1}"
    assert str(dir2).endswith(str(Path("data/users/2/browser_session"))), f"Path mismatch for User 2: {dir2}"
    print(f"  ✅ User 1 Vault: {dir1}")
    print(f"  ✅ User 2 Vault: {dir2}")

def test_session_status_scoping_and_anti_hijacking():
    print("\nTesting Session Status API Scoping & Anti-Hijacking Protection...")
    dir1 = get_user_browser_session_dir(1)
    dir2 = get_user_browser_session_dir(2)

    marker1 = dir1 / "session_verified.json"
    marker2 = dir2 / "session_verified.json"

    # Step A: Ensure User 1 has a verified active session marker
    marker1.write_text(json.dumps({
        "portal": "naukri",
        "connected": True,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "cookie_count": 28,
        "verified_url": "https://www.naukri.com/mnjuser/profile",
        "connection_method": "mobile_headless_otp"
    }), encoding="utf-8")

    # Ensure User 2 has NO session marker (unconfigured)
    if marker2.exists():
        marker2.unlink()

    # Query User 1 status
    res1 = client.get("/api/portals/naukri/session-status", headers=HEADERS_U1)
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["connected"] is True, "User 1 must be connected"
    assert data1["user_id"] == 1
    assert data1["cookie_count"] == 28

    # Query User 2 status: MUST NOT inherit User 1's session (Zero-Theft Guard)
    res2 = client.get("/api/portals/naukri/session-status", headers=HEADERS_U2)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["connected"] is False, "Security Breach: User 2 inherited User 1's Naukri session!"
    assert data2["status"] == "unconfigured"
    assert data2["user_id"] == 2
    print("  ✅ Anti-Hijacking Verification Passed: User 2 cannot access or view User 1's session.")

def test_dual_session_coexistence_and_zero_cross_contamination():
    print("\nTesting Dual Session Coexistence & Zero Cross-Contamination...")
    dir1 = get_user_browser_session_dir(1)
    dir2 = get_user_browser_session_dir(2)

    marker1 = dir1 / "session_verified.json"
    marker2 = dir2 / "session_verified.json"

    # Inject mock distinct session marker into User 2's vault
    marker2.write_text(json.dumps({
        "portal": "naukri",
        "connected": True,
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "cookie_count": 45,
        "verified_url": "https://www.naukri.com/mnjuser/homepage",
        "connection_method": "mobile_headless_otp"
    }), encoding="utf-8")

    # Verify User 1 sees ONLY User 1's cookies (28)
    res1 = client.get("/api/portals/naukri/session-status", headers=HEADERS_U1)
    data1 = res1.json()
    assert data1["connected"] is True
    assert data1["cookie_count"] == 28
    assert data1["user_id"] == 1

    # Verify User 2 sees ONLY User 2's cookies (45)
    res2 = client.get("/api/portals/naukri/session-status", headers=HEADERS_U2)
    data2 = res2.json()
    assert data2["connected"] is True
    assert data2["cookie_count"] == 45
    assert data2["user_id"] == 2

    print("  ✅ Both User 1 and User 2 maintain independent active Naukri sessions simultaneously.")

def test_anti_hijacking_otp_submission_guard():
    print("\nTesting Headless Auth Manager Anti-Hijacking OTP Guard...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def run_otp_guard_test():
        import time
        from unittest.mock import MagicMock
        # Register a mock active session for User 1
        sess_id = "test_sess_user1_mock"
        mock_session = PendingAuthSession(
            session_id=sess_id,
            portal="naukri",
            identifier="9912565635",
            playwright=MagicMock(),
            context=MagicMock(),
            page=MagicMock(),
            created_at=time.time(),
            user_id=1,
            session_dir=get_user_browser_session_dir(1)
        )
        headless_auth_manager._active_sessions[sess_id] = mock_session

        try:
            # Attack Scenario: User 2 attempts to submit OTP to User 1's active login session
            attack_result = await headless_auth_manager.verify_naukri_otp(
                session_id=sess_id,
                otp="123456",
                expected_user_id=2
            )
            assert attack_result["status"] == "ERROR", "Security Breach: Attack was not blocked!"
            assert "Access denied" in attack_result["message"]
            print("  ✅ Anti-Hijacking Guard Blocked Unauthorized OTP Submission: Access Denied.")

            # Legitimate Scenario: User 1 submits to their own session -> Ownership passes check
            # (Fails gracefully on mock page object rather than 403 access denial)
            legit_result = await headless_auth_manager.verify_naukri_otp(
                session_id=sess_id,
                otp="123456",
                expected_user_id=1
            )
            assert "Access denied" not in legit_result.get("message", ""), "Legitimate owner should pass ownership guard"
            print("  ✅ Legitimate User 1 passed ownership verification.")

        finally:
            if sess_id in headless_auth_manager._active_sessions:
                del headless_auth_manager._active_sessions[sess_id]

    loop.run_until_complete(run_otp_guard_test())

def test_isolated_session_disconnection():
    print("\nTesting Isolated Session Disconnection (User 2 disconnects without affecting User 1)...")
    dir1 = get_user_browser_session_dir(1)
    dir2 = get_user_browser_session_dir(2)

    marker1 = dir1 / "session_verified.json"
    marker2 = dir2 / "session_verified.json"

    assert marker1.exists(), "User 1 marker must be present before disconnect"
    assert marker2.exists(), "User 2 marker must be present before disconnect"

    # User 2 disconnects their session
    res_disc = client.post("/api/portals/naukri/disconnect", headers=HEADERS_U2)
    assert res_disc.status_code == 200
    assert res_disc.json()["status"] == "disconnected"
    assert res_disc.json()["user_id"] == 2

    # Verify User 2 marker is deleted
    assert not marker2.exists(), "User 2 session marker must be deleted"
    res2 = client.get("/api/portals/naukri/session-status", headers=HEADERS_U2)
    assert res2.json()["connected"] is False

    # CRITICAL CHECK: User 1 session MUST remain active and 100% untouched!
    assert marker1.exists(), "Security Breach: User 1 session was deleted when User 2 disconnected!"
    res1 = client.get("/api/portals/naukri/session-status", headers=HEADERS_U1)
    assert res1.json()["connected"] is True
    assert res1.json()["cookie_count"] == 28
    print("  ✅ User 2 session successfully disconnected.")
    print("  ✅ User 1 session verified 100% ACTIVE and UNTOUCHED (Zero Blast-Radius).")

if __name__ == "__main__":
    print("=================================================================")
    print("Phase 5 - Step 2: Verification Suite")
    print("=================================================================")
    test_session_directory_vault_isolation()
    test_session_status_scoping_and_anti_hijacking()
    test_dual_session_coexistence_and_zero_cross_contamination()
    test_anti_hijacking_otp_submission_guard()
    test_isolated_session_disconnection()
    print("=================================================================")
    print("🏆 ALL PHASE 5 - STEP 2 VERIFICATION TESTS PASSED (100% SUCCESS)")
    print("=================================================================")
