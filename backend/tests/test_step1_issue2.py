"""
Test Suite: Step 1 - Issue 1.2 Verification
Focus: Naukri Mobile OTP endpoints user_id scoping and session anti-hijacking guard.
"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi import HTTPException
from app.db.session import SessionLocal
from app.db.models import User
from app.schemas.api import NaukriMobileConnectRequest, NaukriVerifyOtpRequest, NaukriCancelSessionRequest
from app.agent.headless_auth import PendingAuthSession, headless_auth_manager
from main import connect_naukri_mobile, verify_naukri_mobile_otp, cancel_naukri_mobile_session

async def test_issue_1_2():
    print("=" * 65, flush=True)
    print("RUNNING STEP 1 - ISSUE 1.2: NAUKRI MOBILE OTP USER_ID ISOLATION", flush=True)
    print("=" * 65, flush=True)

    db = SessionLocal()
    try:
        u1 = db.query(User).filter(User.id == 1).first()
        u2 = db.query(User).filter(User.id == 2).first()
        assert u1 is not None and u2 is not None

        # 1. Test connect_naukri_mobile passes user_id=2 when called by User 2
        with patch.object(headless_auth_manager, "start_naukri_login", new_callable=AsyncMock) as mock_start:
            mock_start.return_value = {
                "status": "OTP_REQUIRED",
                "session_id": "test_session_u2_123",
                "message": "OTP sent",
                "portal": "naukri",
                "user_id": 2
            }
            req = NaukriMobileConnectRequest(identifier="9876543210", password="Password123")
            res = await connect_naukri_mobile(req=req, current_user=u2)
            assert mock_start.called, "FAIL: start_naukri_login was not called"
            call_kwargs = mock_start.call_args.kwargs
            assert call_kwargs.get("user_id") == 2, f"FAIL: Expected user_id=2, got {call_kwargs.get('user_id')}"
            print("[PASS] 1. connect_naukri_mobile correctly passes current_user.id (user_id=2) to start_naukri_login.", flush=True)

        # 2. Test Anti-Hijacking Guard: User 1 cannot verify OTP for User 2's session
        dummy_session = PendingAuthSession(
            session_id="session_belonging_to_user_2",
            portal="naukri",
            identifier="9876543210",
            playwright=None,
            context=None,
            page=None,
            created_at=0.0,
            user_id=2,
            session_dir=Path("backend/data/users/2/browser_session")
        )
        headless_auth_manager._active_sessions["session_belonging_to_user_2"] = dummy_session

        try:
            v_req = NaukriVerifyOtpRequest(session_id="session_belonging_to_user_2", otp="123456")
            try:
                await verify_naukri_mobile_otp(req=v_req, current_user=u1)
                assert False, "FAIL: User 1 was allowed to verify User 2's session!"
            except HTTPException as e:
                assert e.status_code == 403, f"Expected 403 Forbidden, got {e.status_code}"
                print("[PASS] 2. Anti-Hijacking Guard: User 1 blocked from verifying User 2's OTP session (HTTP 403).", flush=True)

            # 3. Test Anti-Hijacking Guard: User 1 cannot cancel User 2's session
            c_req = NaukriCancelSessionRequest(session_id="session_belonging_to_user_2")
            try:
                await cancel_naukri_mobile_session(req=c_req, current_user=u1)
                assert False, "FAIL: User 1 was allowed to cancel User 2's session!"
            except HTTPException as e:
                assert e.status_code == 403, f"Expected 403 Forbidden, got {e.status_code}"
                print("[PASS] 3. Anti-Hijacking Guard: User 1 blocked from cancelling User 2's OTP session (HTTP 403).", flush=True)

            # 4. User 2 CAN verify their own session
            with patch.object(headless_auth_manager, "verify_naukri_otp", new_callable=AsyncMock) as mock_verify:
                mock_verify.return_value = {
                    "status": "SUCCESS",
                    "message": "Verified",
                    "portal": "naukri",
                    "user_id": 2
                }
                v_res = await verify_naukri_mobile_otp(req=v_req, current_user=u2)
                assert v_res.status == "SUCCESS"
                print("[PASS] 4. User 2 successfully verifies their own OTP session.", flush=True)
        finally:
            headless_auth_manager._active_sessions.pop("session_belonging_to_user_2", None)

        print("=" * 65, flush=True)
        print("[SUCCESS] ALL 4 VERIFICATIONS PASSED FOR STEP 1 - ISSUE 1.2!", flush=True)
        print("=" * 65, flush=True)
    finally:
        db.close()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_issue_1_2())
