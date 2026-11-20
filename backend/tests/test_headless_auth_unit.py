"""
Unit test for HeadlessAuthManager
"""
import sys
from pathlib import Path

# Safe Windows stdout encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agent.headless_auth import HeadlessAuthManager, headless_auth_manager

def test_unit():
    print("Testing HeadlessAuthManager instantiation...")
    manager = HeadlessAuthManager()
    assert manager is not None
    assert manager.session_dir.exists()
    
    # Test session cleanup logic
    manager.cleanup_expired_sessions()
    assert len(manager._active_sessions) == 0
    
    # Test verify_naukri_otp with non-existent session
    res = manager.verify_naukri_otp("non_existent_id", "123456")
    print("Non-existent session response:", res)
    assert res["status"] == "ERROR"
    assert "expired or not found" in res["message"]
    
    # Test short OTP validation
    res2 = manager.verify_naukri_otp("any_id", "12")
    assert res2["status"] == "ERROR"
    assert "Invalid OTP format" in res2["message"]
    
    print("✅ All unit tests passed for HeadlessAuthManager!")

if __name__ == "__main__":
    test_unit()

