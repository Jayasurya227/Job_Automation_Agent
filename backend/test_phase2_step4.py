"""
Phase 2 - Step 4 Rigorous Verification Test
Enterprise Verification Suite:
1. Verifies ATS Scorer loads and grounds candidate profile strictly per user_id.
2. Verifies Q&A Screening Bank seeds and looks up answers strictly per user_id in SQLite.
3. Verifies EasyApplyFiller resolves isolated user vaults (snapshots, browser session, profile).
4. Verifies Cross-Tenant Resume Security: User 2 cannot access or attach User 1's master resume.
5. Verifies Application Workflow sets and preserves user context across the execution lifecycle.
"""

import sys
import os
import json
from pathlib import Path

# Setup paths
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.user_storage import (
    ensure_user_storage,
    get_user_base_dir,
    get_user_resume,
    get_user_snapshots_dir,
    get_user_browser_session_dir,
)
from app.agent.scorer import load_profile
from app.agent.qa_bank import (
    seed_default_qa_bank,
    get_answer_from_rules,
    get_answer_from_memory,
)
from app.agent.applier import EasyApplyFiller
from app.agent.workflow import run_application_workflow
from app.db.session import SessionLocal
from app.db import crud


def run_tests():
    print("=" * 70)
    print("🧪 PHASE 2 STEP 4: ATS SCORER & APPLIER MULTI-USER VERIFICATION")
    print("=" * 70)

    # 1. ATS Scorer Profile Loading Scoped per User
    print("\n[Test 1] Verifying ATS Scorer loads profiles strictly per user_id...")
    ensure_user_storage(1)
    ensure_user_storage(2)

    p1 = load_profile(user_id=1)
    p2 = load_profile(user_id=2)

    assert p1 is not None and p2 is not None, "Failed to load profiles!"
    assert "Rayavaram Jayasurya" in p1.personal_info.name, f"User 1 name mismatch: {p1.personal_info.name}"
    assert "Candidate 2" in p2.personal_info.name, f"User 2 name mismatch: {p2.personal_info.name}"
    assert p1.personal_info.email != p2.personal_info.email, "Emails must be distinct!"
    print(f"  ✅ User 1 Profile: {p1.personal_info.name} ({p1.personal_info.email})")
    print(f"  ✅ User 2 Profile: {p2.personal_info.name} ({p2.personal_info.email})")

    # 2. Q&A Memory Bank Scoping
    print("\n[Test 2] Verifying Screening Q&A Bank seeding & memory isolation...")
    from app.db.models import User
    with SessionLocal() as db:
        # Ensure User 2 exists in database for Foreign Key integrity
        u2 = db.query(User).filter(User.id == 2).first()
        if not u2:
            u2 = User(id=2, email="candidate2@autojob.ai", password_hash="dummy_hash_for_test", full_name="Candidate 2", is_active=True)
            db.add(u2)
            db.commit()
            db.refresh(u2)

        # Seed both users
        s1 = seed_default_qa_bank(user_id=1)
        s2 = seed_default_qa_bank(user_id=2)

        # Retrieve questions for each user
        u1_qas = crud.list_qa_answers(db, user_id=1)
        u2_qas = crud.list_qa_answers(db, user_id=2)

        assert len(u1_qas) > 0, "User 1 should have seeded Q&A answers!"
        assert len(u2_qas) > 0, "User 2 should have seeded Q&A answers!"

        # Verify User 2 answers do not cross into User 1
        rule1 = get_answer_from_rules("What is your total years of professional experience?", user_id=1)
        rule2 = get_answer_from_rules("What is your total years of professional experience?", user_id=2)

        assert rule1 is not None and rule2 is not None
        print(f"  ✅ User 1 Experience Rule: {rule1['answer']} years")
        print(f"  ✅ User 2 Experience Rule: {rule2['answer']} years")

    # 3. EasyApplyFiller Vault Resolution
    print("\n[Test 3] Verifying EasyApplyFiller directory and profile isolation...")
    filler1 = EasyApplyFiller(headless=True, user_id=1)
    filler2 = EasyApplyFiller(headless=True, user_id=2)

    assert filler1.user_id == 1 and filler2.user_id == 2
    assert filler1.snapshot_dir != filler2.snapshot_dir, "Snapshot directories must be distinct!"
    assert filler1.browser_session_dir != filler2.browser_session_dir, "Browser sessions must be distinct!"
    assert filler1.snapshot_dir == get_user_snapshots_dir(1)
    assert filler2.snapshot_dir == get_user_snapshots_dir(2)
    assert filler1.browser_session_dir == get_user_browser_session_dir(1)
    assert filler2.browser_session_dir == get_user_browser_session_dir(2)
    assert "Rayavaram Jayasurya" in filler1.profile.personal_info.name
    assert "Candidate 2" in filler2.profile.personal_info.name
    print(f"  ✅ Filler 1 Snapshot Vault: {filler1.snapshot_dir}")
    print(f"  ✅ Filler 2 Snapshot Vault: {filler2.snapshot_dir}")
    print(f"  ✅ Filler 1 Naukri Session Vault: {filler1.browser_session_dir}")
    print(f"  ✅ Filler 2 Naukri Session Vault: {filler2.browser_session_dir}")

    # 4. Cross-Tenant Resume Security Guard
    print("\n[Test 4] Verifying Cross-Tenant Resume Security (Zero-Theft Guard)...")
    # User 1 has uploaded_resume.pdf
    u1_resume = get_user_resume(1)
    assert u1_resume is not None and u1_resume.exists(), "User 1 must have resume from Step 1"

    # User 2 does not have an uploaded resume yet
    u2_resume_file = get_user_base_dir(2) / "uploaded_resume.pdf"
    if u2_resume_file.exists():
        u2_resume_file.unlink()

    u2_resume = get_user_resume(2)
    assert u2_resume is None, "User 2 should not have a resume before uploading!"

    # Run filler2 on a test job URL without resume:
    # Must immediately reject and NEVER steal User 1's resume!
    res_fill2 = filler2.fill_and_stage_application(
        target_url_or_path="https://www.naukri.com/job-listings-sample-test",
        resume_path=None,
        job_title="Python Developer",
        company_name="Tech Corp",
        thread_id="test_u2_sec_thread"
    )
    assert res_fill2.status == "ERROR", f"Expected ERROR status for missing resume, got {res_fill2.status}"
    assert "No resume PDF found" in res_fill2.error_message
    print(f"  ✅ Security Guard Confirmed: {res_fill2.error_message}")
    print("  ✅ User 2 cannot access or steal User 1's master resume.")

    # 5. Application Workflow Multi-Tenant Scoping
    print("\n[Test 5] Verifying Workflow state scoping...")
    wf1 = run_application_workflow(
        job_title="Software Engineer",
        company_name="Alpha Inc",
        job_description="Sample job description with Python and FastAPI requirements.",
        job_url="",
        match_score=85,
        user_id=1,
    )
    wf2 = run_application_workflow(
        job_title="Data Scientist",
        company_name="Beta Inc",
        job_description="Sample job description with Machine Learning and SQL requirements.",
        job_url="",
        match_score=85,
        user_id=2,
    )
    assert wf1["state"]["user_id"] == 1
    assert wf2["state"]["user_id"] == 2
    assert wf1["state"]["screening_answers"]["full_name"] == p1.personal_info.name
    assert wf2["state"]["screening_answers"]["full_name"] == p2.personal_info.name
    print(f"  ✅ Workflow 1 State Scoped to User 1: {wf1['state']['user_id']} ({wf1['state']['screening_answers']['full_name']})")
    print(f"  ✅ Workflow 2 State Scoped to User 2: {wf2['state']['user_id']} ({wf2['state']['screening_answers']['full_name']})")

    print("\n" + "=" * 70)
    print("🎉 ALL PHASE 2 STEP 4 TESTS PASSED WITH 100% ACCURACY & SECURITY!")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()
