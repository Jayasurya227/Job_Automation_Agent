"""
Test Suite: Step 1 - Issue 1.3 Verification
Focus: Indeed Session Vault Isolation, User Scoping, and Anti-Hijacking Guard.
"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import json
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi import HTTPException
from app.db.session import SessionLocal
from app.db.models import User
from app.core.user_storage import get_user_indeed_session_dir
from app.schemas.api import IndeedMobileConnectRequest, IndeedVerifyOtpRequest, IndeedCancelSessionRequest
from app.agent.headless_auth import PendingAuthSession, headless_auth_manager
from main import (
    get_indeed_session_status,
    launch_indeed_session,
    connect_indeed_mobile,
    verify_indeed_mobile_otp,
    cancel_indeed_mobile_session,
)

async def test_issue_1_3():
    print("=" * 65, flush=True)
    print("RUNNING STEP 1 - ISSUE 1.3: INDEED SESSION VAULT & AUTH ISOLATION", flush=True)
    print("=" * 65, flush=True)

    db = SessionLocal()
    try:
        u1 = db.query(User).filter(User.id == 1).first()
        u2 = db.query(User).filter(User.id == 2).first()
        assert u1 is not None and u2 is not None

        # 1. Directory isolation check
        u1_dir = get_user_indeed_session_dir(1)
        u2_dir = get_user_indeed_session_dir(2)
        assert u1_dir != u2_dir
        assert "users\\1" in str(u1_dir) or "users/1" in str(u1_dir)
        assert "users\\2" in str(u2_dir) or "users/2" in str(u2_dir)
        print("[PASS] 1. get_user_indeed_session_dir isolates storage paths per user.", flush=True)

        # 2. Session status isolation: Simulate User 1 connected, User 2 unconfigured
        marker_1 = u1_dir / "session_verified.json"
        marker_2 = u2_dir / "session_verified.json"
        if marker_2.exists():
            marker_2.unlink()
        marker_1.write_text(json.dumps({
            "portal": "Indeed",
            "connected": True,
            "verified_at": "2026-11-18T12:00:00+00:00",
            "cookie_count": 8,
        }), encoding="utf-8")

        status_u1 = get_indeed_session_status(current_user=u1)
        status_u2 = get_indeed_session_status(current_user=u2)

        assert status_u1["connected"] is True, f"User 1 expected connected=True, got {status_u1}"
        assert status_u2["connected"] is False, f"User 2 expected connected=False, got {status_u2}"
        print("[PASS] 2. get_indeed_session_status isolates status (User 1 = connected, User 2 = unconfigured).", flush=True)

        # 3. Test connect_indeed_mobile passes user_id=2 when called by User 2
        with patch.object(headless_auth_manager, "start_indeed_login", new_callable=AsyncMock) as mock_start:
            mock_start.return_value = {
                "status": "OTP_REQUIRED",
                "session_id": "test_indeed_session_u2",
                "message": "Code sent",
                "portal": "indeed",
                "user_id": 2,
            }
            req = IndeedMobileConnectRequest(identifier="user2@example.com", password="Password123")
            res = await connect_indeed_mobile(req=req, current_user=u2)

            assert mock_start.called, "FAIL: start_indeed_login was not called"
            call_kwargs = mock_start.call_args.kwargs
            assert call_kwargs.get("user_id") == 2, f"FAIL: Expected user_id=2, got {call_kwargs.get('user_id')}"
            print("[PASS] 3. connect_indeed_mobile correctly passes current_user.id (user_id=2) to start_indeed_login.", flush=True)

        # 4. Anti-Hijacking Guard: User 1 cannot verify OTP for User 2's session
        dummy_session = PendingAuthSession(
            session_id="indeed_session_belonging_to_user_2",
            portal="indeed",
            identifier="user2@example.com",
            playwright=None,
            context=None,
            page=None,
            created_at=0.0,
            user_id=2,
            session_dir=u2_dir,
        )
        headless_auth_manager._active_sessions["indeed_session_belonging_to_user_2"] = dummy_session

        try:
            v_req = IndeedVerifyOtpRequest(session_id="indeed_session_belonging_to_user_2", verification_code="123456")
            try:
                await verify_indeed_mobile_otp(req=v_req, current_user=u1)
                assert False, "FAIL: User 1 was allowed to verify User 2's Indeed session!"
            except HTTPException as e:
                assert e.status_code == 403, f"Expected 403 Forbidden, got {e.status_code}"
                print("[PASS] 4. Anti-Hijacking Guard: User 1 blocked from verifying User 2's Indeed session (HTTP 403).", flush=True)

            # 5. Anti-Hijacking Guard: User 1 cannot cancel User 2's session
            c_req = IndeedCancelSessionRequest(session_id="indeed_session_belonging_to_user_2")
            try:
                await cancel_indeed_mobile_session(req=c_req, current_user=u1)
                assert False, "FAIL: User 1 was allowed to cancel User 2's Indeed session!"
            except HTTPException as e:
                assert e.status_code == 403, f"Expected 403 Forbidden, got {e.status_code}"
                print("[PASS] 5. Anti-Hijacking Guard: User 1 blocked from cancelling User 2's Indeed session (HTTP 403).", flush=True)

            # 6. User 2 CAN verify their own session
            with patch.object(headless_auth_manager, "verify_indeed_otp", new_callable=AsyncMock) as mock_verify:
                mock_verify.return_value = {
                    "status": "SUCCESS",
                    "message": "Verified",
                    "portal": "indeed",
                    "user_id": 2,
                }
                v_res = await verify_indeed_mobile_otp(req=v_req, current_user=u2)
                assert v_res.status == "SUCCESS"
                print("[PASS] 6. User 2 successfully verifies their own Indeed session.", flush=True)
        finally:
            headless_auth_manager._active_sessions.pop("indeed_session_belonging_to_user_2", None)

        print("=" * 65, flush=True)
        print("[SUCCESS] ALL 6 VERIFICATIONS PASSED FOR STEP 1 - ISSUE 1.3!", flush=True)
        print("=" * 65, flush=True)
    finally:
        db.close()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_issue_1_3())
