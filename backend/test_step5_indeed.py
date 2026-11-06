"""
Test Step 5: Indeed Mobile Authentication Endpoints & Schemas Verification.
"""
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from main import app
from app.schemas.api import (
    IndeedMobileConnectRequest,
    IndeedVerifyOtpRequest,
    IndeedCancelSessionRequest,
    IndeedConnectResponse,
)
from app.agent.headless_auth import HeadlessAuthManager, headless_auth_manager


def test_indeed_schemas():
    """Verify Indeed Pydantic schemas validate correctly."""
    # 1. Connect request
    req1 = IndeedMobileConnectRequest(identifier="jayasurya@gmail.com", password="mypassword123")
    assert req1.identifier == "jayasurya@gmail.com"
    assert req1.password == "mypassword123"
    assert req1.use_code is False

    req2 = IndeedMobileConnectRequest(identifier="9876543210", use_code=True)
    assert req2.use_code is True
    assert req2.password is None

    # 2. Verify request with code or otp alias
    v_req1 = IndeedVerifyOtpRequest(session_id="test-session-123", code="123456")
    assert v_req1.verification_code == "123456"

    v_req2 = IndeedVerifyOtpRequest(session_id="test-session-123", otp="654321")
    assert v_req2.verification_code == "654321"

    # 3. Response schema
    resp = IndeedConnectResponse(
        status="OTP_REQUIRED",
        message="Verification code sent",
        session_id="test-uuid",
        portal="indeed",
        cookie_count=15
    )
    assert resp.status == "OTP_REQUIRED"
    assert resp.portal == "indeed"
    assert resp.session_id == "test-uuid"
    print("✅ All Indeed schemas verified successfully!")


def test_indeed_headless_manager_methods():
    """Verify HeadlessAuthManager has Indeed methods & properties."""
    mgr = HeadlessAuthManager()
    assert hasattr(mgr, "start_indeed_login")
    assert hasattr(mgr, "verify_indeed_otp")
    assert hasattr(mgr, "indeed_session_dir")
    assert mgr.indeed_session_dir.exists()
    print("✅ HeadlessAuthManager Indeed methods verified!")


def test_indeed_api_routes():
    """Verify Indeed API endpoints are registered on FastAPI app routes."""
    routes = {getattr(r, "path", None) for r in app.routes}
    assert "/api/portals/indeed/connect-mobile" in routes, "Missing /api/portals/indeed/connect-mobile"
    assert "/api/portals/indeed/verify-otp" in routes, "Missing /api/portals/indeed/verify-otp"
    assert "/api/portals/indeed/cancel-mobile" in routes, "Missing /api/portals/indeed/cancel-mobile"
    assert "/api/portals/indeed/session-status" in routes, "Missing /api/portals/indeed/session-status"
    print("✅ All Indeed FastAPI endpoints registered in route table!")


if __name__ == "__main__":
    test_indeed_schemas()
    test_indeed_headless_manager_methods()
    test_indeed_api_routes()
    print("\n🎉 ALL STEP 5 INDEED TESTS PASSED 100%!")
