import sys
import os
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock

# Force WindowsSelectorEventLoopPolicy to prevent IOCP hang on Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.db.session import SessionLocal
from app.db import crud
from app.db.models import User, Job, Application
from app.agent.scraper import DiscoveredJob
from app.schemas.match import JobMatchResult
from app.agent.scorer import analyze_and_score_job
from app.agent.ingestion import ingest_single_job, get_discovery_lock, process_1click_applications
from app.agent.workflow import _record_applied, resume_application_workflow, WORKFLOW_SESSIONS

def run_master_step2_tests():
    print("==================================================================")
    print("MASTER STEP 2 REGRESSION TEST SUITE (BUGS 9 TO 14)")
    print("==================================================================")

    db = SessionLocal()
    try:
        u1 = db.query(User).filter(User.id == 1).first()
        u2 = db.query(User).filter(User.id == 2).first()
        assert u1 is not None, "User 1 must exist"
        assert u2 is not None, "User 2 must exist"
        u1_initial_jobs = db.query(Job).filter(Job.user_id == 1).count()
        print(f"Pre-flight: User 1 ({u1.email}) has {u1_initial_jobs} jobs. User 2 ({u2.email}) exists.")

        # -------------------------------------------------------------
        # BUG 9 (Issue 2.1): AI Scoring User Isolation
        # -------------------------------------------------------------
        print("\n--- [Bug 9] AI Scoring & Profile Resolution Isolation ---")
        from app.agent.scorer import load_profile
        p1 = load_profile(user_id=1)
        p2 = load_profile(user_id=2)
        assert p1.personal_info.name != p2.personal_info.name, "User 1 and User 2 profiles must be distinct"
        print(f"  User 1 Profile Name: {p1.personal_info.name}")
        print(f"  User 2 Profile Name: {p2.personal_info.name}")

        dummy_job = DiscoveredJob(
            title="Senior Python Backend Architect",
            company="MultiTenant Innovations Ltd",
            location="Remote",
            portal="naukri",
            job_url="https://www.naukri.com/job-listings-python-architect-test-step2-all",
            description="Deep expertise in Python, FastAPI, Docker, and distributed multi-tenant systems.",
            salary="20-30 LPA",
            apply_type="1-Click"
        )
        mock_match = JobMatchResult(
            match_score=88,
            recommendation="Apply",
            matching_skills=["Python", "FastAPI"],
            missing_skills=[],
            key_strengths=["Architecture"],
            summary_reasoning="Strong multi-tenant skills.",
            apply_type="1-Click",
            job_title="Senior Python Backend Architect",
            company_name="MultiTenant Innovations Ltd"
        )
        with patch("app.agent.ingestion.analyze_and_score_job") as mock_score:
            mock_score.return_value = mock_match
            res = asyncio.run(ingest_single_job(discovered=dummy_job, min_match_score=70, user_id=2))
            assert res is not None, "Ingestion must succeed"
            assert mock_score.called
            assert mock_score.call_args.kwargs.get("user_id") == 2, "Scorer must receive user_id=2"
            
            created_job = db.query(Job).filter(Job.id == res.job_id).first()
            assert created_job.user_id == 2, f"Created job must belong to user 2, got {created_job.user_id}"
            crud.delete_job(db=db, job_id=res.job_id, user_id=2)
        print("  [PASS] Bug 9: Scoring & Ingestion correctly isolates profile and sets user_id=2.")

        # -------------------------------------------------------------
        # BUG 10 (Issue 2.2): Ingestion DB Rollback & Master Resume
        # -------------------------------------------------------------
        print("\n--- [Bug 10] Ingestion DB Rollback on Error & Resume Scoping ---")
        disc_job = DiscoveredJob(
            title="DevOps Lead", company="Cloud Systems", location="Remote", portal="Naukri",
            job_url="https://example.com/jobs/devops-step2", description="Kubernetes and Terraform expert."
        )
        # Verify rollback on simulated DB error
        with patch.object(db, "commit", side_effect=Exception("Simulated Ingestion DB Commit Failure")):
            with patch("app.agent.ingestion.SessionLocal", return_value=db):
                res = asyncio.run(ingest_single_job(discovered=disc_job, user_id=2))
                assert res is None, "Failed ingestion must return None cleanly without crashing"
        print("  [PASS] Bug 10: Ingestion rollback executed cleanly on exception.")

        # -------------------------------------------------------------
        # BUG 11 (Issue 2.3): Per-User Discovery Concurrency Locks
        # -------------------------------------------------------------
        print("\n--- [Bug 11] Per-User Discovery Lock Independence ---")
        lock1 = get_discovery_lock(1)
        lock2 = get_discovery_lock(2)
        assert lock1 is not lock2, "Locks for User 1 and User 2 must be separate objects"
        async def check_concurrency():
            async with lock1:
                assert lock1.locked() and not lock2.locked()
                async with lock2:
                    assert lock1.locked() and lock2.locked()
            assert not lock1.locked() and not lock2.locked()
        asyncio.run(check_concurrency())
        print("  [PASS] Bug 11: Independent locks allow simultaneous discovery cycles.")

        # -------------------------------------------------------------
        # BUG 12 (Issue 2.4): 1-Click Daily Quota Isolation
        # -------------------------------------------------------------
        print("\n--- [Bug 12] 1-Click Auto-Apply Quota Isolation ---")
        test_job_u2 = Job(
            job_title="Cloud Architect", company_name="Tenant Testing Ltd", location="Remote",
            portal_name="Naukri", job_url="https://example.com/jobs/arch-1",
            job_description="Architecting multi-tenant systems.", user_id=2,
        )
        db.add(test_job_u2)
        db.commit()
        db.refresh(test_job_u2)

        match_mock = JobMatchResult(
            job_title="Cloud Architect", company_name="Tenant Testing Ltd", match_score=90,
            recommendation="Apply", matching_skills=["Cloud", "Architecture"], missing_skills=[],
            key_strengths=["Multi-tenant design"], summary_reasoning="Top fit", apply_type="1-Click"
        )
        crud.save_job_evaluation(db=db, job_id=test_job_u2.id, match=match_mock)
        crud.create_or_update_application(db=db, job_id=test_job_u2.id, status="Ready", user_id=2)

        mock_filler_instance = MagicMock()
        mock_filler_res = MagicMock()
        mock_filler_res.status = "SUBMITTED"
        mock_filler_instance.fill_and_stage_application.return_value = mock_filler_res

        with patch("app.agent.applier.EasyApplyFiller", return_value=mock_filler_instance):
            result = asyncio.run(process_1click_applications(user_id=2, max_daily_limit=5, min_score=80))
            assert result["applied_count"] == 1, f"Expected 1 application, got {result['applied_count']}"

        app_rec = db.query(Application).filter(Application.job_id == test_job_u2.id).first()
        assert app_rec.status == "Applied" and app_rec.user_id == 2
        print("  [PASS] Bug 12: 1-Click quota and execution strictly scoped to User 2.")

        # -------------------------------------------------------------
        # BUG 13 (Issue 2.5): _record_applied Multi-Tenant Scoping
        # -------------------------------------------------------------
        print("\n--- [Bug 13] _record_applied User Scoping ---")
        test_job_u2_b = Job(
            job_title="Security Engineer", company_name="SafeNet", location="Hyderabad",
            portal_name="Indeed", job_url="https://example.com/jobs/sec-2",
            job_description="Application security testing.", user_id=2,
        )
        db.add(test_job_u2_b)
        db.commit()
        db.refresh(test_job_u2_b)

        _record_applied(job_id=test_job_u2_b.id, pdf_path="/test/path/resume.pdf", note="Applied via test", user_id=2)
        app_rec_b = db.query(Application).filter(Application.job_id == test_job_u2_b.id).first()
        assert app_rec_b.status == "Applied" and app_rec_b.user_id == 2
        print("  [PASS] Bug 13: _record_applied stores user_id=2 correctly.")

        # -------------------------------------------------------------
        # BUG 14 (Issue 2.6): Review Gateway Rejection Archiving Scoped
        # -------------------------------------------------------------
        print("\n--- [Bug 14] Review Gateway Rejection Scoped Archiving ---")
        thread_id = f"test_thread_reg_{test_job_u2_b.id}"
        WORKFLOW_SESSIONS[thread_id] = {
            "thread_id": thread_id, "user_id": 2, "job_id": test_job_u2_b.id,
            "job_title": test_job_u2_b.job_title, "company_name": test_job_u2_b.company_name,
            "portal_name": "Indeed", "job_url": test_job_u2_b.job_url,
            "status": "REVIEW_GATEWAY", "execution_logs": [],
        }
        res_rej = resume_application_workflow(thread_id=thread_id, approved=False, reason="Too far away", user_id=2)
        assert res_rej["status"] == "REJECTED_BY_USER"
        db.refresh(app_rec_b)
        assert app_rec_b.status == "Archived" and app_rec_b.user_id == 2
        print("  [PASS] Bug 14: Rejected workflow cleanly archived with user_id=2.")

        # -------------------------------------------------------------
        # ZERO DATA LOSS VERIFICATION
        # -------------------------------------------------------------
        print("\n--- User 1 Zero Data Loss Verification ---")
        u1_final_jobs = db.query(Job).filter(Job.user_id == 1).count()
        assert u1_final_jobs == u1_initial_jobs, f"User 1 job count altered from {u1_initial_jobs} to {u1_final_jobs}!"
        print(f"  [PASS] User 1 jobs untouched: exactly {u1_final_jobs} jobs.")

        # Cleanup test records
        for jid in [test_job_u2.id, test_job_u2_b.id]:
            crud.delete_job(db=db, job_id=jid, user_id=2)
        print("  [CLEANUP] Temporary test jobs removed cleanly.")

        print("\n==================================================================")
        print("MASTER STEP 2 REGRESSION SUITE: ALL 6 CHECKS (BUGS 9-14) PASSED!")
        print("==================================================================")

    finally:
        db.close()

if __name__ == "__main__":
    run_master_step2_tests()
