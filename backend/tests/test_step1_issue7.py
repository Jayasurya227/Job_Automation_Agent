"""
Test Suite: Step 1 - Issue 1.7 Verification
Focus: Settings Endpoint Per-User Isolation (account_settings.json).
"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.db.session import SessionLocal
from app.db.models import User
from app.core.user_storage import get_user_base_dir
from app.schemas.api import UpdateAccountSettingsRequest
from main import get_user_settings, update_user_settings

def test_issue_1_7():
    print("=" * 65, flush=True)
    print("RUNNING STEP 1 - ISSUE 1.7: ACCOUNT SETTINGS PER-USER ISOLATION", flush=True)
    print("=" * 65, flush=True)

    db = SessionLocal()
    u2_settings_file = get_user_base_dir(2) / "account_settings.json"
    try:
        u1 = db.query(User).filter(User.id == 1).first()
        u2 = db.query(User).filter(User.id == 2).first()
        assert u1 is not None and u2 is not None

        # 1. User 1 settings should have User 1's data
        s1 = get_user_settings(current_user=u1)
        assert s1["smtp"]["sender_email"] == "updated.candidate@gmail.com"
        print("[PASS] 1. User 1 settings successfully read from isolated/migrated vault.", flush=True)

        # 2. User 2 should NOT see User 1's email or settings
        s2 = get_user_settings(current_user=u2)
        assert s2["smtp"]["sender_email"] != "updated.candidate@gmail.com"
        print("[PASS] 2. User 2 settings are isolated (Zero leak of User 1 SMTP email).", flush=True)

        # 3. User 2 updates their settings
        update_req = UpdateAccountSettingsRequest(
            smtp_sender_email="candidate2@example.com",
            smtp_sender_name="Candidate Two",
            smtp_app_password="password_for_u2_mock",
            smtp_daily_limit=15,
            smtp_enabled=True,
        )
        res = update_user_settings(req=update_req, current_user=u2)
        assert res["status"] == "success"
        assert res["settings"]["smtp"]["sender_email"] == "candidate2@example.com"
        assert u2_settings_file.exists()
        print("[PASS] 3. User 2 updates saved strictly to users/2/account_settings.json.", flush=True)

        # 4. Verify User 1's settings remained completely unchanged
        s1_after = get_user_settings(current_user=u1)
        assert s1_after["smtp"]["sender_email"] == "updated.candidate@gmail.com"
        assert s1_after["smtp"]["daily_limit"] == 12
        print("[PASS] 4. User 1 settings 100% intact (Zero cross-contamination).", flush=True)

        print("=" * 65, flush=True)
        print("[SUCCESS] ALL 4 VERIFICATIONS PASSED FOR STEP 1 - ISSUE 1.7!", flush=True)
        print("=" * 65, flush=True)
    finally:
        if u2_settings_file.exists():
            u2_settings_file.unlink()
        db.close()

if __name__ == "__main__":
    test_issue_1_7()
