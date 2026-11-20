"""
Module: test_phase2_step1.py
Purpose: Verification for Phase 2 Step 1 (User Directory & Safe Migration).
"""
import sys
import shutil
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from app.core.user_storage import (
    ensure_user_storage,
    get_user_base_dir,
    get_user_profile_path,
    get_user_resume_path,
    get_user_browser_session_dir,
    get_user_snapshots_dir,
    get_user_tailored_resumes_dir,
    USERS_ROOT_DIR
)

def run_step1_verification():
    print("=" * 60)
    print("🚀 RUNNING PHASE 2 - STEP 1 VERIFICATION")
    print("=" * 60)

    # 1. Test User 1 directory creation & safe migration
    print("\n🔍 1. Initializing User 1 storage and migrating data...")
    u1_storage = ensure_user_storage(1)
    
    assert u1_storage["base_dir"].exists(), "User 1 base directory missing!"
    print(f" User 1 Base Directory: {u1_storage['base_dir']}")

    assert u1_storage["profile_path"].exists(), "User 1 profile.json missing after migration!"
    u1_prof_size = u1_storage["profile_path"].stat().st_size
    assert u1_prof_size > 0, "User 1 profile.json is empty!"
    print(f" User 1 Profile migrated successfully ({u1_prof_size} bytes)")

    assert u1_storage["resume_path"].exists(), "User 1 uploaded_resume.pdf missing after migration!"
    u1_res_size = u1_storage["resume_path"].stat().st_size
    assert u1_res_size > 0, "User 1 uploaded_resume.pdf is empty!"
    print(f" User 1 Resume migrated successfully ({u1_res_size} bytes)")

    assert u1_storage["browser_session_dir"].exists(), "User 1 browser_session dir missing!"
    u1_session_count = len(list(u1_storage["browser_session_dir"].iterdir()))
    print(f" User 1 Naukri browser session migrated ({u1_session_count} files/dirs)")

    assert u1_storage["snapshots_dir"].exists(), "User 1 snapshots dir missing!"
    print(f" User 1 Snapshots directory ready: {u1_storage['snapshots_dir']}")

    assert u1_storage["tailored_resumes_dir"].exists(), "User 1 tailored_resumes dir missing!"
    print(f" User 1 Tailored resumes directory ready: {u1_storage['tailored_resumes_dir']}")

    # 2. Test Multi-User Isolation for User 2 (Candidate 2)
    print("\n🔍 2. Testing Isolation for User 2 (Candidate 2)...")
    u2_base = get_user_base_dir(2)
    u2_storage = ensure_user_storage(2)

    assert u2_base.exists(), "User 2 base dir was not created!"
    assert u2_storage["profile_path"] != u1_storage["profile_path"], "Profile paths must be distinct!"
    assert u2_storage["browser_session_dir"] != u1_storage["browser_session_dir"], "Browser session paths must be distinct!"
    print(f" User 2 Base Directory isolated: {u2_storage['base_dir']}")
    print(f" User 2 Browser Session isolated: {u2_storage['browser_session_dir']}")

    # Clean up test user 2 to keep workspace pristine
    if u2_base.exists():
        shutil.rmtree(u2_base)
        print(" Test User 2 temporary directory cleaned up.")

    print("\n" + "=" * 60)
    print("🎉 PHASE 2 - STEP 1 VERIFICATION COMPLETED 100% SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_step1_verification()
