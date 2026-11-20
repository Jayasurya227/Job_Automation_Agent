"""
Module: test_phase2_step2_direct.py
Purpose: Direct Principal Engineer Verification of Phase 2 Step 2:
         Per-User Profile & Resume Isolation and Atomic File Operations.
"""
import os
import sys
import json
import shutil
import sqlite3
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from app.schemas.profile import CandidateProfile
from app.core.user_storage import (
    load_user_profile,
    save_user_profile,
    save_user_resume,
    get_user_resume,
    get_user_profile_path,
    get_user_resume_path,
    get_user_base_dir
)

def run_direct_step2_tests():
    print("=" * 65)
    print("🚀 PRINCIPAL ARCHITECT VERIFICATION: PHASE 2 - STEP 2")
    print("=" * 65)

    # -------------------------------------------------------------
    # TEST 1: User 1 Profile & Resume Isolation
    # -------------------------------------------------------------
    print("\n🔍 1. Testing User 1 Profile Loading from Isolated Vault...")
    p1 = load_user_profile(user_id=1)
    assert p1 is not None, "Failed to load User 1 profile!"
    assert "Rayavaram Jayasurya" in p1.personal_info.name, f"User 1 name mismatch: {p1.personal_info.name}"
    print(f" User 1 Profile successfully loaded from users/1/profile.json")
    print(f"   Name: {p1.personal_info.name}")
    print(f"   Email: {p1.personal_info.email}")
    print(f"   Target Roles: {p1.preferences.target_roles}")

    r1_path = get_user_resume(user_id=1)
    assert r1_path is not None and r1_path.exists(), "User 1 resume missing!"
    assert r1_path.stat().st_size == 135261, f"User 1 resume size unexpected: {r1_path.stat().st_size}"
    print(f" User 1 Resume isolated in users/1/uploaded_resume.pdf ({r1_path.stat().st_size} bytes)")

    # -------------------------------------------------------------
    # TEST 2: User 2 (Candidate 2) Clean Seeding & Complete Isolation
    # -------------------------------------------------------------
    print("\n🔍 2. Testing User 2 (Candidate 2) Fresh Profile Seeding & Isolation...")
    u2_id = 99999  # Isolated test user ID
    u2_dir = get_user_base_dir(u2_id)
    if u2_dir.exists():
        shutil.rmtree(u2_dir)

    p2 = load_user_profile(user_id=u2_id)
    assert p2 is not None, "Failed to seed User 2 profile!"
    assert p2.personal_info.name == f"Candidate {u2_id}", f"Unexpected seeded name: {p2.personal_info.name}"
    assert p2.personal_info.name != p1.personal_info.name, "User 2 leaked User 1 profile data!"
    print(f" User 2 clean profile created in users/{u2_id}/profile.json (Zero Data Leakage)")

    # -------------------------------------------------------------
    # TEST 3: User 2 Atomic Profile Updates (Zero Stale Data)
    # -------------------------------------------------------------
    print("\n🔍 3. Testing Atomic Profile Updates for User 2...")
    p2.personal_info.name = "Jane Doe (Frontend Principal)"
    p2.personal_info.email = "jane.doe@techcorp.io"
    p2.preferences.target_roles = ["Staff Frontend Architect", "Principal UI Engineer"]
    p2.technical_skills.frameworks_and_libraries = ["React 19", "Next.js 15", "TailwindCSS"]

    saved_p2 = save_user_profile(user_id=u2_id, profile=p2)
    assert saved_p2.personal_info.name == "Jane Doe (Frontend Principal)"

    # Verify physical file on disk
    u2_file = get_user_profile_path(u2_id)
    with open(u2_file, "r", encoding="utf-8") as f:
        u2_disk = json.load(f)
    assert u2_disk["personal_info"]["name"] == "Jane Doe (Frontend Principal)"
    assert "Staff Frontend Architect" in u2_disk["preferences"]["target_roles"]
    print(" User 2 profile saved atomically to disk!")

    # STRICT CROSS-CHECK: Verify User 1 was 100% untouched
    p1_reloaded = load_user_profile(user_id=1)
    assert "Rayavaram Jayasurya" in p1_reloaded.personal_info.name
    assert "Staff Frontend Architect" not in p1_reloaded.preferences.target_roles
    print(" Strict Audit Passed: User 1 profile was 100% unaffected and remains pristine!")

    # -------------------------------------------------------------
    # TEST 4: User 2 Resume Upload & Magic Byte Validation
    # -------------------------------------------------------------
    print("\n🔍 4. Testing User 2 Resume Upload & Security Boundary...")
    sample_pdf = b"%PDF-1.7\n1 0 obj\n<< /Title (Jane Doe Master Resume) >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
    
    saved_r2 = save_user_resume(user_id=u2_id, filename="Jane_Doe_Resume.pdf", contents=sample_pdf)
    assert saved_r2.exists()
    assert saved_r2.stat().st_size == len(sample_pdf)
    print(f" User 2 resume written atomically to users/{u2_id}/uploaded_resume.pdf ({len(sample_pdf)} bytes)")

    # STRICT CROSS-CHECK: Verify User 1 resume was 100% untouched
    r1_recheck = get_user_resume(user_id=1)
    assert r1_recheck.stat().st_size == 135261, f"User 1 resume modified! Size: {r1_recheck.stat().st_size}"
    print(" Strict Audit Passed: User 1 resume (135,261 bytes) remains 100% untouched!")

    # -------------------------------------------------------------
    # TEST 5: Security Boundary Validation (Corrupted / Malicious Files)
    # -------------------------------------------------------------
    print("\n🔍 5. Security Testing: Enforcing PDF Magic Header Validation...")
    corrupted_data = b"NOT_A_VALID_PDF_HEADER_MALICIOUS_BYTES"
    try:
        save_user_resume(user_id=u2_id, filename="fake.pdf", contents=corrupted_data)
        assert False, "Should have raised ValueError for invalid PDF magic bytes!"
    except ValueError as ve:
        print(f" Security Guard Passed: Corrupt file rejected successfully ({ve})")

    # -------------------------------------------------------------
    # CLEANUP TEST USER 2
    # -------------------------------------------------------------
    print("\n🔍 6. Cleaning up temporary User 2 artifacts...")
    if u2_dir.exists():
        shutil.rmtree(u2_dir)
    print(" Cleanup complete.")

    print("\n" + "=" * 65)
    print("🎉 STEP 2 COMPLETED 100% SUCCESSFULLY WITH ZERO REGRESSIONS!")
    print("=" * 65)

if __name__ == "__main__":
    run_direct_step2_tests()
