import sys
import os
import asyncio
from pathlib import Path

# Force WindowsSelectorEventLoopPolicy to prevent IOCP hang on Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.db.session import SessionLocal
from app.db import crud
from app.db.models import User, Job, Application
from app.agent.ingestion import get_discovery_lock, process_1click_applications
from app.agent.workflow import _record_applied, resume_application_workflow, WORKFLOW_SESSIONS
from unittest.mock import patch, MagicMock

def run_tests():
    print("==================================================================")
    print("STEP 2 (Issues 2.3 - 2.6) VERIFICATION TEST SUITE")
    print("==================================================================")

    db = SessionLocal()
    try:
        u1 = db.query(User).filter(User.id == 1).first()
        u2 = db.query(User).filter(User.id == 2).first()
        assert u1 is not None, "User 1 (Rayavaram Jayasurya) must exist"
        assert u2 is not None, "User 2 must exist"
        u1_initial_jobs = db.query(Job).filter(Job.user_id == 1).count()
        print(f"Initial State: User 1 ({u1.email}) has {u1_initial_jobs} jobs.")

        # -------------------------------------------------------------
        # TEST 1: Per-User Discovery Locks (Issue 2.3)
        # -------------------------------------------------------------
        print("\n--- Test 1: Per-User Discovery Locks (Concurrency Isolation) ---")
        lock1 = get_discovery_lock(1)
        lock2 = get_discovery_lock(2)
        assert lock1 is not lock2, "FAIL: User 1 and User 2 must have independent discovery locks!"

        # Acquire lock1
        async def test_locks():
            async with lock1:
                assert lock1.locked(), "Lock 1 must be locked"
                assert not lock2.locked(), "FAIL: Lock 2 must NOT be locked when Lock 1 is acquired!"
                # User 2 can acquire lock2 simultaneously
                async with lock2:
                    assert lock2.locked(), "Lock 2 must be locked concurrently"
            assert not lock1.locked() and not lock2.locked(), "Both locks must be released"

        asyncio.run(test_locks())
        print("  [PASS] User 1 and User 2 can acquire discovery locks independently without blocking each other.")

        # -------------------------------------------------------------
        # TEST 2: Daily Quota & 1-Click Isolation (Issue 2.4)
        # -------------------------------------------------------------
        print("\n--- Test 2: process_1click_applications User Quota Isolation ---")
        # Check quota count isolated per user
        u1_quota = crud.get_applied_today_count(db, user_id=1)
        u2_quota = crud.get_applied_today_count(db, user_id=2)
        print(f"  Quota applied today: User 1 = {u1_quota}, User 2 = {u2_quota}")

        # Create a test job for User 2 with Ready status
        test_job_u2 = Job(
            job_title="Senior React Engineer",
            company_name="MultiTenant Corp",
            location="Remote",
            portal_name="Naukri",
            job_url="https://example.com/jobs/react-123",
            job_description="Looking for an experienced React developer.",
            user_id=2,
        )
        db.add(test_job_u2)
        db.commit()
        db.refresh(test_job_u2)

        from app.schemas.match import JobMatchResult
        match_mock = JobMatchResult(
            job_title="Senior React Engineer",
            company_name="MultiTenant Corp",
            match_score=85,
            recommendation="Apply",
            matching_skills=["React", "TypeScript"],
            missing_skills=[],
            key_strengths=["Frontend architecture"],
            summary_reasoning="Great fit for candidate.",
            apply_type="1-Click",
        )
        crud.save_job_evaluation(db=db, job_id=test_job_u2.id, match=match_mock)
        crud.create_or_update_application(db=db, job_id=test_job_u2.id, status="Ready", user_id=2)

        # Mock EasyApplyFiller to return SUBMITTED
        mock_filler_instance = MagicMock()
        mock_res = MagicMock()
        mock_res.status = "SUBMITTED"
        mock_filler_instance.fill_and_stage_application.return_value = mock_res

        with patch("app.agent.applier.EasyApplyFiller", return_value=mock_filler_instance):
            result = asyncio.run(process_1click_applications(user_id=2, max_daily_limit=5, min_score=80))

        assert result["user_id"] == 2, f"Result must report user_id=2, got {result['user_id']}"
        assert result["applied_count"] == 1, f"Expected 1 application applied for user 2, got {result['applied_count']}"

        # Verify application in db is scoped to user_id=2
        app_u2 = db.query(Application).filter(Application.job_id == test_job_u2.id).first()
        assert app_u2 is not None, "Application record must exist"
        assert app_u2.status == "Applied", f"Status must be Applied, got {app_u2.status}"
        assert app_u2.user_id == 2, f"Application user_id must be 2, got {app_u2.user_id}"

        # Verify User 1 quota was untouched
        u1_quota_after = crud.get_applied_today_count(db, user_id=1)
        assert u1_quota_after == u1_quota, f"User 1 quota must remain {u1_quota}, got {u1_quota_after}"
        print("  [PASS] process_1click_applications submitted job strictly for User 2; User 1 untouched.")

        # -------------------------------------------------------------
        # TEST 3: _record_applied Scoped to user_id (Issue 2.5)
        # -------------------------------------------------------------
        print("\n--- Test 3: _record_applied User Scoping ---")
        test_job_u2_2 = Job(
            job_title="Backend Python Developer",
            company_name="Isolated Labs",
            location="Bangalore",
            portal_name="Indeed",
            job_url="https://example.com/jobs/python-456",
            job_description="Python FastAPI backend developer role.",
            user_id=2,
        )
        db.add(test_job_u2_2)
        db.commit()
        db.refresh(test_job_u2_2)

        _record_applied(job_id=test_job_u2_2.id, pdf_path="/test/path/resume.pdf", note="Applied via automated test", user_id=2)

        app_rec = db.query(Application).filter(Application.job_id == test_job_u2_2.id).first()
        assert app_rec is not None, "Application must be created"
        assert app_rec.status == "Applied", f"Status must be Applied, got {app_rec.status}"
        assert app_rec.user_id == 2, f"FAIL: Application user_id must be 2, got {app_rec.user_id}"
        print("  [PASS] _record_applied accurately persisted application with user_id=2.")

        # -------------------------------------------------------------
        # TEST 4: Low Match Archiving & Review Rejection Scoped (Issue 2.6)
        # -------------------------------------------------------------
        print("\n--- Test 4: Low Match Archiving & Review Rejection User Scoping ---")
        test_job_u2_3 = Job(
            job_title="Junior Go Developer",
            company_name="Cloud Native Inc",
            location="Remote",
            portal_name="Naukri",
            job_url="https://example.com/jobs/go-789",
            job_description="Go development.",
            user_id=2,
        )
        db.add(test_job_u2_3)
        db.commit()
        db.refresh(test_job_u2_3)

        # Stage in WORKFLOW_SESSIONS for resume workflow
        thread_id = f"test_thread_{test_job_u2_3.id}"
        WORKFLOW_SESSIONS[thread_id] = {
            "thread_id": thread_id,
            "user_id": 2,
            "job_id": test_job_u2_3.id,
            "job_title": test_job_u2_3.job_title,
            "company_name": test_job_u2_3.company_name,
            "portal_name": "Naukri",
            "job_url": test_job_u2_3.job_url,
            "status": "REVIEW_GATEWAY",
            "execution_logs": [],
        }

        # Candidate rejects application
        resume_res = resume_application_workflow(thread_id=thread_id, approved=False, reason="Not interested", user_id=2)
        assert resume_res["status"] == "REJECTED_BY_USER", f"Expected REJECTED_BY_USER, got {resume_res['status']}"

        # Verify job is archived for user 2
        app_rejected = db.query(Application).filter(Application.job_id == test_job_u2_3.id).first()
        assert app_rejected is not None, "Application record must exist"
        assert app_rejected.status == "Archived", f"Application status must be Archived, got {app_rejected.status}"
        assert app_rejected.user_id == 2, f"Application user_id must be 2, got {app_rejected.user_id}"
        print("  [PASS] resume_application_workflow rejection correctly archived job with user_id=2.")

        # -------------------------------------------------------------
        # TEST 5: Verify User 1 Zero Data Loss Guarantee
        # -------------------------------------------------------------
        print("\n--- Test 5: User 1 Zero Data Loss Verification ---")
        u1_final_jobs = db.query(Job).filter(Job.user_id == 1).count()
        assert u1_final_jobs == u1_initial_jobs, f"FAIL: User 1 jobs changed from {u1_initial_jobs} to {u1_final_jobs}!"
        print(f"  [PASS] User 1 jobs count intact: exactly {u1_final_jobs} jobs.")

        # Clean up test jobs for User 2
        for jid in [test_job_u2.id, test_job_u2_2.id, test_job_u2_3.id]:
            crud.delete_job(db=db, job_id=jid, user_id=2)
        print("  [CLEANUP] Temporary test jobs removed cleanly.")

        print("\n==================================================================")
        print("ALL TESTS IN STEP 2 (Issues 2.3 - 2.6) PASSED PERFECTLY!")
        print("==================================================================")

    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
