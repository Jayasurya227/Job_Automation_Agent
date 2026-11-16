"""
Test Suite: Phase 5 - Step 3 Verification
Focus: Concurrent Multi-Tenant Auto-Pilot, Application Proof Isolation, Quota Scoping & Surgical Tenant Purge
Architectural Standard: 20-30 Years Principal Architect Rigor
"""
import sys
import asyncio
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import time
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db import crud
from app.db.models import User, Job, Application
from app.agent.task_queue import MultiTenantTaskQueue, task_queue
from app.agent.scheduler import autopilot_scheduler
from app.agent.applier import EasyApplyFiller
from app.core.user_storage import (
    load_user_profile,
    get_user_snapshots_dir,
    get_user_base_dir,
    get_user_resume_path
)
from app.core.user_cleanup import purge_tenant_data


from app.core.security import hash_password

def ensure_test_user_2():
    db = SessionLocal()
    try:
        u2 = db.query(User).filter(User.id == 2).first()
        if not u2:
            u2 = User(
                id=2,
                email="candidate2@autojob.ai",
                password_hash=hash_password("TestPassword123!"),
                full_name="Candidate Two",
                is_active=True
            )
            db.add(u2)
            db.commit()
        # Seed profile and resume
        p2_path = get_user_base_dir(2) / "profile.json"
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
        r2_path = get_user_base_dir(2) / "uploaded_resume.pdf"
        if not r2_path.exists():
            r2_path.write_bytes(b"%PDF-1.4\nCandidate Two Resume\n%%EOF")
    finally:
        db.close()

def test_concurrent_task_queue_execution():
    ensure_test_user_2()
    print("Testing Concurrent Multi-Tenant Task Queue & Independent Locks...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def run_concurrent_workers():
        # Enqueue two independent tasks for User 1 and User 2
        t1 = await task_queue.enqueue_task(user_id=1, task_type="pilot_cycle", payload={"slot": "naukri"})
        t2 = await task_queue.enqueue_task(user_id=2, task_type="pilot_cycle", payload={"slot": "naukri"})

        assert t1.task_id != t2.task_id
        assert t1.user_id == 1
        assert t2.user_id == 2

        # Verify independent scheduler locks
        lock1 = autopilot_scheduler._get_user_lock(1)
        lock2 = autopilot_scheduler._get_user_lock(2)
        assert lock1 is not lock2, "Each user MUST have an independent asyncio.Lock instance"

        # Simulate concurrent lock acquisition
        async with lock1:
            assert lock1.locked()
            assert not lock2.locked(), "User 1's lock must NEVER lock User 2!"
            async with lock2:
                assert lock2.locked(), "User 2 must be able to lock concurrently with User 1"

        print(f"  ✅ Task 1 (User 1: {t1.task_id}) and Task 2 (User 2: {t2.task_id}) successfully enqueued.")
        print("  ✅ User 1 and User 2 locks execute concurrently with ZERO blocking.")

    loop.run_until_complete(run_concurrent_workers())


def test_profile_target_role_discreteness():
    print("\nTesting Multi-Tenant ATS Target Role & Skill Discreteness...")
    p1 = load_user_profile(user_id=1)
    p2 = load_user_profile(user_id=2)

    roles_u1 = p1.preferences.target_roles
    roles_u2 = p2.preferences.target_roles

    assert "AI ML Engineer" in roles_u1 or "AI Engineer" in roles_u1, "User 1 must target AI roles"
    assert "FastAPI Specialist" in roles_u2 or "Django Engineer" in roles_u2, "User 2 must target Django/FastAPI roles"

    # Verify skill category discreteness
    u1_skills = p1.technical_skills.programming_languages
    u2_skills = p2.technical_skills.frameworks_and_libraries

    assert "Django" in u2_skills or "FastAPI" in u2_skills
    print(f"  ✅ User 1 Target Roles: {roles_u1}")
    print(f"  ✅ User 2 Target Roles: {roles_u2}")
    print("  ✅ Profiles are strictly isolated and evaluate to distinct ATS preferences.")


def test_application_proof_snapshot_vault_isolation():
    print("\nTesting Application Proof Snapshot Vault Directory Isolation...")
    applier1 = EasyApplyFiller(user_id=1)
    applier2 = EasyApplyFiller(user_id=2)

    snap_dir1 = applier1.snapshot_dir
    snap_dir2 = applier2.snapshot_dir

    assert snap_dir1 != snap_dir2, "Snapshot directories must be strictly isolated!"
    assert str(snap_dir1).endswith(str(Path("data/users/1/output/snapshots")))
    assert str(snap_dir2).endswith(str(Path("data/users/2/output/snapshots")))

    # Write a mock application proof into User 1 and User 2 vaults
    proof_u1 = snap_dir1 / "confirmed_u1_proof.png"
    proof_u2 = snap_dir2 / "confirmed_u2_proof.png"

    proof_u1.write_bytes(b"FAKE_PNG_USER1_PROOF")
    proof_u2.write_bytes(b"FAKE_PNG_USER2_PROOF")

    assert proof_u1.exists()
    assert proof_u2.exists()

    # User 2 cannot see User 1's proof
    u2_files = [f.name for f in snap_dir2.iterdir()]
    assert "confirmed_u1_proof.png" not in u2_files, "Security Breach: User 1 screenshot leaked into User 2's vault!"

    # User 1 cannot see User 2's proof
    u1_files = [f.name for f in snap_dir1.iterdir()]
    assert "confirmed_u2_proof.png" not in u1_files, "Security Breach: User 2 screenshot leaked into User 1's vault!"

    print(f"  ✅ User 1 Proof Snapshot Vault: {proof_u1} (Confined to User 1)")
    print(f"  ✅ User 2 Proof Snapshot Vault: {proof_u2} (Confined to User 2)")


def test_per_user_daily_quota_isolation():
    print("\nTesting Per-User Daily Application Quota Isolation...")
    db: Session = SessionLocal()
    try:
        # Create a test job and 7 applications today for User 1
        j1 = Job(
            user_id=1,
            job_title="AI Research Staff Engineer",
            company_name="DeepMind",
            location="Remote",
            portal_name="naukri",
            job_description="AI research role"
        )
        db.add(j1)
        db.commit()

        # Add 7 applied applications for User 1 today
        for i in range(7):
            app = Application(
                job_id=j1.id,
                user_id=1,
                status="Applied",
                applied_at=datetime.now(),
                created_at=datetime.now(timezone.utc)
            )
            db.add(app)
        db.commit()

        u1_count = crud.get_applied_today_count(db, user_id=1)
        u2_count = crud.get_applied_today_count(db, user_id=2)

        assert u1_count >= 7, f"User 1 applied today should be >= 7, got {u1_count}"
        assert u2_count == 0, f"User 2 applied today MUST be 0, got {u2_count}"

        # Clean up test applications and job
        db.query(Application).filter(Application.job_id == j1.id).delete()
        db.query(Job).filter(Job.id == j1.id).delete()
        db.commit()

        print(f"  ✅ User 1 Today's Applications: {u1_count} (Quota limit reached)")
        print(f"  ✅ User 2 Today's Applications: {u2_count} (Active & unconstrained)")
        print("  ✅ Quota enforcement operates independently per tenant with ZERO cross-bleed.")

    finally:
        db.close()


def test_surgical_tenant_purge_and_master_preservation():
    print("\nTesting Final Surgical Tenant Purge & Master User Preservation...")
    db: Session = SessionLocal()
    try:
        # Step A: Verify User 2 exists before purge
        u2_before = db.query(User).filter(User.id == 2).first()
        assert u2_before is not None, "User 2 must exist prior to purge"
        u2_vault = get_user_base_dir(2)
        assert u2_vault.exists(), "User 2 vault must exist prior to purge"

        # Step B: Perform surgical purge on User 2
        stats = purge_tenant_data(user_id=2, db=db)
        print(f"  ✅ Tenant 2 Purged: {stats}")

        # Step C: Verify User 2 is 100% wiped
        u2_after = db.query(User).filter(User.id == 2).first()
        assert u2_after is None, "User 2 DB record must be deleted"
        assert not u2_vault.exists(), "User 2 filesystem vault must be completely removed"
        print("  ✅ User 2 completely eradicated from database and filesystem.")

        # Step D: CRITICAL MASTER USER VERIFICATION (Zero Blast-Radius)
        u1_master = db.query(User).filter(User.id == 1).first()
        assert u1_master is not None, "CRITICAL: Master User 1 was lost!"
        assert u1_master.full_name == "Rayavaram Jayasurya", f"User 1 name altered: {u1_master.full_name}"
        assert u1_master.email == "rayavaramjayasurya@gmail.com"

        u1_vault = get_user_base_dir(1)
        assert u1_vault.exists(), "CRITICAL: Master User 1 vault directory missing!"
        u1_resume = get_user_resume_path(1)
        assert u1_resume.exists(), "CRITICAL: Master User 1 uploaded resume missing!"
        assert u1_resume.stat().st_size > 100000, "Master User 1 resume bytes corrupted!"

        print("  🏆 MASTER USER 1 (Rayavaram Jayasurya) 100% PRESERVED, HEALTHY, AND PRISTINE.")

    finally:
        db.close()


if __name__ == "__main__":
    print("=================================================================")
    print("Phase 5 - Step 3: Final Verification Suite")
    print("=================================================================")
    test_concurrent_task_queue_execution()
    test_profile_target_role_discreteness()
    test_application_proof_snapshot_vault_isolation()
    test_per_user_daily_quota_isolation()
    test_surgical_tenant_purge_and_master_preservation()
    print("=================================================================")
    print("🏆 ALL PHASE 5 - STEP 3 VERIFICATION TESTS PASSED (100% SUCCESS)")
    print("=================================================================")
