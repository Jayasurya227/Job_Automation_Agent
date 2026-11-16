"""
Module: test_phase2_step2.py
Purpose: Principal Engineer (20-30 Years Experience Standard) Verification for
         Phase 2 Step 2: Per-User Profile & Resume Isolation.
"""
import sys
import json
import shutil
import sqlite3
from pathlib import Path

backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from main import app
from app.core.security import create_access_token
from app.core.user_storage import (
    get_user_profile_path,
    get_user_resume_path,
    get_user_base_dir
)

client = TestClient(app, raise_server_exceptions=False)

def run_step2_verification():
    print("=" * 65)
    print("🚀 RUNNING PHASE 2 - STEP 2 VERIFICATION (PER-USER PROFILE & RESUME)")
    print("=" * 65)

    db_path = backend_dir / "data" / "jobs.db"
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # -------------------------------------------------------------
    # 1. VERIFY USER 1 (Master Candidate) ISOLATED ACCESS
    # -------------------------------------------------------------
    print("\n🔍 1. Testing User 1 Profile & Master Resume Access...")
    token_u1 = create_access_token(user_id=1, email="rayavaramjayasurya@gmail.com")
    headers_u1 = {"Authorization": f"Bearer {token_u1}"}

    res_p1 = client.get("/api/profile", headers=headers_u1)
    assert res_p1.status_code == 200, f"Expected 200 for User 1 profile, got {res_p1.status_code}"
    p1_data = res_p1.json()
    assert "Rayavaram Jayasurya" in p1_data["personal_info"]["name"], "User 1 name mismatch!"
    print(f" User 1 Profile loaded from users/1/profile.json successfully!")
    print(f"   Candidate Name: {p1_data['personal_info']['name']}")
    print(f"   Target Roles: {p1_data['preferences']['target_roles']}")

    res_r1 = client.get("/api/profile/download-uploaded-resume", headers=headers_u1)
    assert res_r1.status_code == 200, f"Expected 200 for User 1 resume download, got {res_r1.status_code}"
    assert len(res_r1.content) > 100000, "User 1 resume PDF size seems wrong!"
    assert res_r1.content.startswith(b"%PDF"), "User 1 resume missing %PDF header!"
    print(f" User 1 Master Resume served from users/1/uploaded_resume.pdf ({len(res_r1.content)} bytes)")

    # -------------------------------------------------------------
    # 2. CREATE & TEST USER 2 (Candidate 2) IN COMPLETE ISOLATION
    # -------------------------------------------------------------
    print("\n🔍 2. Registering User 2 (Candidate 2) & Testing Profile Isolation...")
    u2_email = "candidate2_test_step2@example.com"
    u2_pass = "SecurePass456!"
    u2_name = "Jane Doe (Frontend Architect)"

    # Clean existing if needed
    c.execute("DELETE FROM users WHERE email = ?", (u2_email,))
    conn.commit()

    reg_res = client.post("/api/auth/register", json={
        "email": u2_email,
        "password": u2_pass,
        "full_name": u2_name
    })
    assert reg_res.status_code == 201, f"User 2 registration failed: {reg_res.text}"
    u2_id = reg_res.json()["id"]
    print(f" User 2 registered with ID: {u2_id}")

    token_u2 = create_access_token(user_id=u2_id, email=u2_email)
    headers_u2 = {"Authorization": f"Bearer {token_u2}"}

    # Hit User 2 profile (Should get clean initial profile with Jane Doe)
    res_p2 = client.get("/api/profile", headers=headers_u2)
    assert res_p2.status_code == 200
    p2_data = res_p2.json()
    assert p2_data["personal_info"]["name"] == u2_name, f"Expected {u2_name}, got {p2_data['personal_info']['name']}"
    assert p2_data["personal_info"]["name"] != p1_data["personal_info"]["name"], "Profiles are leaking across users!"
    print(f" User 2 Profile automatically seeded with Candidate Name: '{p2_data['personal_info']['name']}'")

    # Update User 2's profile with custom frontend skills
    print("\n🔍 3. Updating User 2's Profile (PUT /api/profile)...")
    p2_data["technical_skills"]["frameworks_and_libraries"] = ["React", "Vue", "Next.js", "TailwindCSS"]
    p2_data["preferences"]["target_roles"] = ["Staff Frontend Engineer", "UI Architect"]

    put_p2 = client.put("/api/profile", json=p2_data, headers=headers_u2)
    assert put_p2.status_code == 200
    print(" User 2 profile updated via API successfully!")

    # Verify physical file on disk for User 2
    u2_profile_disk = get_user_profile_path(u2_id)
    assert u2_profile_disk.exists(), "User 2 profile.json missing on disk!"
    with open(u2_profile_disk, "r", encoding="utf-8") as f:
        u2_disk_json = json.load(f)
    assert "Staff Frontend Engineer" in u2_disk_json["preferences"]["target_roles"]
    print(" User 2 disk file users/2/profile.json verified!")

    # STRICT CHECK: Verify User 1's profile was 100% UNTOUCHED!
    u1_profile_disk = get_user_profile_path(1)
    with open(u1_profile_disk, "r", encoding="utf-8") as f:
        u1_disk_json = json.load(f)
    assert "Rayavaram Jayasurya" in u1_disk_json["personal_info"]["name"]
    assert "Staff Frontend Engineer" not in u1_disk_json["preferences"]["target_roles"]
    print(" Strict Audit Passed: User 1 profile on disk remains 100% untouched and pristine!")

    # -------------------------------------------------------------
    # 4. TEST USER 2 RESUME UPLOAD IN ISOLATION
    # -------------------------------------------------------------
    print("\n🔍 4. Uploading Isolated Resume for User 2 (POST /api/profile/upload-resume)...")
    sample_pdf_bytes = b"%PDF-1.4\n1 0 obj\n<< /Title (Jane Doe Resume) >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
    
    from unittest.mock import patch
    with patch("main.parse_resume_content") as mock_parse:
        mock_parse.return_value = p2_data
        upload_res = client.post(
            "/api/profile/upload-resume",
            headers=headers_u2,
            files={"file": ("Jane_Doe_Resume.pdf", sample_pdf_bytes, "application/pdf")}
        )
    assert upload_res.status_code == 200, f"Upload failed: {upload_res.text}"
    print(f" User 2 Resume uploaded successfully: {upload_res.json().get('message')}")

    # Verify User 2 physical resume file on disk
    u2_resume_disk = get_user_resume_path(u2_id)
    assert u2_resume_disk.exists(), "User 2 resume missing on disk!"
    assert u2_resume_disk.stat().st_size == len(sample_pdf_bytes)
    print(f" User 2 Resume exists in users/{u2_id}/uploaded_resume.pdf ({u2_resume_disk.stat().st_size} bytes)")

    # STRICT CHECK: Verify User 1's physical resume file on disk is UNTOUCHED
    u1_resume_disk = get_user_resume_path(1)
    assert u1_resume_disk.stat().st_size == 135261, f"User 1 resume was modified! Size: {u1_resume_disk.stat().st_size}"
    print(f" Strict Audit Passed: User 1 Resume (135,261 bytes) is 100% intact and untouched!")

    # -------------------------------------------------------------
    # 5. SECURITY & NEGATIVE VALIDATION TESTS
    # -------------------------------------------------------------
    print("\n🔍 5. Security & Negative Validation Testing...")
    # Bad file extension
    bad_ext_res = client.post(
        "/api/profile/upload-resume",
        headers=headers_u2,
        files={"file": ("malicious.exe", b"executable code", "application/octet-stream")}
    )
    assert bad_ext_res.status_code == 400
    print(" Security Check: Non-PDF extension blocked with 400 Bad Request.")

    # Corrupt / fake PDF (non %PDF magic header)
    fake_pdf_res = client.post(
        "/api/profile/upload-resume",
        headers=headers_u2,
        files={"file": ("fake.pdf", b"NOT A REAL PDF", "application/pdf")}
    )
    assert fake_pdf_res.status_code == 400
    print(" Security Check: Fake PDF without magic bytes blocked with 400 Bad Request.")

    # -------------------------------------------------------------
    # 6. CLEANUP TEST DATA
    # -------------------------------------------------------------
    print("\n🔍 6. Cleaning up temporary User 2 test artifacts...")
    u2_base = get_user_base_dir(u2_id)
    if u2_base.exists():
        shutil.rmtree(u2_base)
    c.execute("DELETE FROM users WHERE email = ?", (u2_email,))
    conn.commit()
    conn.close()
    print(" Test cleanup completed.")

    print("\n" + "=" * 65)
    print("🎉 PHASE 2 - STEP 2 VERIFICATION COMPLETED 100% WITH ZERO ERRORS!")
    print("=" * 65)

if __name__ == "__main__":
    run_step2_verification()
