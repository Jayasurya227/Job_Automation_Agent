"""
Test Suite: Phase 5 - Step 1 Verification
Focus: Two-User Provisioning, Cryptographic JWT Scoping, and Complete Vault Isolation
Architectural Standard: 20-30 Years Principal Architect Rigor
"""
import sys
import asyncio
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from main import app
from app.db.session import SessionLocal
from app.db.models import User, Job, Application
from app.core.security import create_access_token, decode_access_token
from app.core.user_storage import (
    load_user_profile,
    get_user_profile_path,
    get_user_resume_path,
    get_user_base_dir
)
from app.core.user_cleanup import purge_tenant_data

client = TestClient(app)

def ensure_test_user_2(db: Session) -> User:
    u2 = db.query(User).filter(User.id == 2).first()
    if not u2:
        from app.core.security import hash_password
        u2 = User(
            id=2,
            email="candidate2@autojob.ai",
            password_hash=hash_password("TestPassword123!"),
            full_name="Candidate Two",
            is_active=True
        )
        db.add(u2)
        db.commit()
    p2_path = get_user_profile_path(2)
    if not p2_path.exists():
        import json
        p2_path.write_text(json.dumps({
            "personal_info": {"name": "Candidate Two", "email": "candidate2@autojob.ai"},
            "preferences": {"target_roles": ["FastAPI Specialist", "Django Engineer"]},
            "technical_skills": {
                "programming_languages": ["Python", "SQL"],
                "frameworks_and_libraries": ["Django", "FastAPI"],
                "ai_and_ml": [], "databases": ["PostgreSQL"],
                "tools_and_platforms": ["Docker"], "soft_skills": []
            }
        }, indent=2), encoding="utf-8")
    r2_path = get_user_resume_path(2)
    if not r2_path.exists():
        r2_path.write_bytes(b"%PDF-1.4\nCandidate Two Test Resume\n%%EOF")
    return u2

def test_user_provisioning_and_jwt_tokens():
    print("Testing User 1 and User 2 cryptographic JWT token scoping...")
    db: Session = SessionLocal()
    try:
        ensure_test_user_2(db)
        user1 = db.query(User).filter(User.id == 1).first()
        user2 = db.query(User).filter(User.id == 2).first()

        assert user1 is not None, "Master User 1 must exist in DB"
        assert user2 is not None, "Test User 2 must exist in DB"

        assert user1.full_name == "Rayavaram Jayasurya", f"User 1 full name mismatch: {user1.full_name}"
        assert user1.email == "rayavaramjayasurya@gmail.com"

        assert user2.full_name == "Candidate 2" or user2.full_name == "Candidate Two"
        assert user2.email == "candidate2@autojob.ai"

        # Generate tokens
        token1 = create_access_token(user_id=user1.id, email=user1.email)
        token2 = create_access_token(user_id=user2.id, email=user2.email)

        payload1 = decode_access_token(token1)
        payload2 = decode_access_token(token2)

        assert payload1["sub"] == "1", "User 1 token must decode to sub=1"
        assert payload2["sub"] == "2", "User 2 token must decode to sub=2"
        assert payload1["sub"] != payload2["sub"], "Tokens must be isolated"
        print("✅ JWT authentication token scoping verified.")
    finally:
        db.close()

def test_profile_vault_isolation_api():
    print("Testing REST API Profile Vault Isolation (User 1 vs User 2)...")
    token1 = create_access_token(user_id=1, email="rayavaramjayasurya@gmail.com")
    token2 = create_access_token(user_id=2, email="candidate2@autojob.ai")

    # User 1 profile request
    res1 = client.get("/api/profile", headers={"Authorization": f"Bearer {token1}"})
    assert res1.status_code == 200, f"User 1 profile request failed: {res1.text}"
    data1 = res1.json()
    assert data1["personal_info"]["name"] == "Rayavaram Jayasurya"
    assert "rayavaramjayasurya@gmail.com" in data1["personal_info"]["email"]
    assert "Candidate Two" not in res1.text, "User 1 profile must not contain Candidate Two"

    # User 2 profile request
    res2 = client.get("/api/profile", headers={"Authorization": f"Bearer {token2}"})
    assert res2.status_code == 200, f"User 2 profile request failed: {res2.text}"
    data2 = res2.json()
    assert data2["personal_info"]["name"] == "Candidate Two"
    assert data2["personal_info"]["email"] == "candidate2@autojob.ai"
    assert "Rayavaram Jayasurya" not in res2.text, "User 2 profile must not contain Rayavaram Jayasurya"
    assert "rayavaramjayasurya@gmail.com" not in res2.text, "User 2 profile must not leak User 1 email"
    print("✅ REST API Profile isolation verified (Zero Data-Leakage).")

def test_resume_vault_zero_theft_isolation():
    print("Testing Resume Vault Isolation & Zero-Theft Guard...")
    token1 = create_access_token(user_id=1, email="rayavaramjayasurya@gmail.com")
    token2 = create_access_token(user_id=2, email="candidate2@autojob.ai")

    # User 1 downloads their resume
    res1 = client.get("/api/profile/download-uploaded-resume", headers={"Authorization": f"Bearer {token1}"})
    assert res1.status_code == 200, f"User 1 download failed: {res1.text}"
    assert res1.headers["content-type"] == "application/pdf"
    assert len(res1.content) > 100000, "User 1 must download the master resume PDF (>100KB)"

    # User 2 downloads their resume
    res2 = client.get("/api/profile/download-uploaded-resume", headers={"Authorization": f"Bearer {token2}"})
    assert res2.status_code == 200, f"User 2 download failed: {res2.text}"
    assert res2.headers["content-type"] == "application/pdf"
    assert b"Candidate Two" in res2.content, "User 2 must download Candidate Two's distinct resume"
    assert len(res2.content) != len(res1.content), "User 1 and User 2 resumes must have distinct byte sizes"
    print("✅ Resume vault zero-theft isolation verified.")

def test_database_row_level_multi_tenant_isolation():
    print("Testing Database Row-Level Multi-Tenant Isolation...")
    db: Session = SessionLocal()
    token1 = create_access_token(user_id=1, email="rayavaramjayasurya@gmail.com")
    token2 = create_access_token(user_id=2, email="candidate2@autojob.ai")

    test_job_1 = None
    test_job_2 = None
    try:
        # Create isolated job for User 1
        test_job_1 = Job(
            user_id=1,
            job_title="Lead AI Engineer - Jayasurya Unique",
            company_name="Google Cloud AI",
            location="Hyderabad",
            job_url="https://naukri.com/job-1-unique",
            portal_name="naukri",
            job_description="AI Lead position"
        )
        db.add(test_job_1)

        # Create isolated job for User 2
        test_job_2 = Job(
            user_id=2,
            job_title="Senior Django Developer - Candidate2 Unique",
            company_name="Red Hat",
            location="Bengaluru",
            job_url="https://naukri.com/job-2-unique",
            portal_name="naukri",
            job_description="Django Senior position"
        )
        db.add(test_job_2)
        db.commit()

        # Query User 1 jobs via API
        res1 = client.get("/api/jobs", headers={"Authorization": f"Bearer {token1}"})
        assert res1.status_code == 200
        titles1 = [j["job_title"] for j in res1.json()]
        assert "Lead AI Engineer - Jayasurya Unique" in titles1, "User 1 must see User 1's jobs"
        assert "Senior Django Developer - Candidate2 Unique" not in titles1, "User 1 must NOT see User 2's jobs"

        # Query User 2 jobs via API
        res2 = client.get("/api/jobs", headers={"Authorization": f"Bearer {token2}"})
        assert res2.status_code == 200
        titles2 = [j["job_title"] for j in res2.json()]
        assert "Senior Django Developer - Candidate2 Unique" in titles2, "User 2 must see User 2's jobs"
        assert "Lead AI Engineer - Jayasurya Unique" not in titles2, "User 2 must NOT see User 1's jobs"

        print("✅ Database Row-Level multi-tenant query isolation verified.")

    finally:
        if test_job_1 and test_job_1.id:
            db.query(Job).filter(Job.id == test_job_1.id).delete()
        if test_job_2 and test_job_2.id:
            db.query(Job).filter(Job.id == test_job_2.id).delete()
        db.commit()
        db.close()

def test_master_user_safety_guard_and_tenant_cleanup():
    print("Testing Master User Safety Guard & Surgical Tenant Cleanup...")
    db: Session = SessionLocal()
    try:
        # Guard: Attempting to delete Master User (ID 1) must raise PermissionError
        with pytest.raises(PermissionError):
            purge_tenant_data(user_id=1, db=db, allow_master_purge=False)
        print("  - Master User 1 deletion shield: ACTIVE & VERIFIED.")

        # Test transient tenant cleanup (ID 999)
        dummy_dir = get_user_base_dir(999)
        dummy_file = dummy_dir / "profile.json"
        dummy_file.write_text('{"name": "Temporary Test"}', encoding="utf-8")
        assert dummy_dir.exists()

        stats = purge_tenant_data(user_id=999, db=db)
        assert stats["vault_directory_removed"] is True
        assert not dummy_dir.exists(), "Dummy tenant vault must be completely removed"
        print("  - Surgical tenant cleanup utility: ACTIVE & VERIFIED.")

    finally:
        db.close()

if __name__ == "__main__":
    print("=================================================================")
    print("Phase 5 - Step 1: Verification Suite")
    print("=================================================================")
    test_user_provisioning_and_jwt_tokens()
    test_profile_vault_isolation_api()
    test_resume_vault_zero_theft_isolation()
    test_database_row_level_multi_tenant_isolation()
    test_master_user_safety_guard_and_tenant_cleanup()
    print("=================================================================")
    print("🏆 ALL PHASE 5 - STEP 1 VERIFICATION TESTS PASSED (100% SUCCESS)")
    print("=================================================================")
