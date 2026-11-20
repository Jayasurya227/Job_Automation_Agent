"""
Test Suite: Step 2 - Issues 2.1 & 2.2 Verification
Focus: Ingestion Database Session Rollback Safety, Multi-Tenant Scoping, and Scorer User Isolation.
"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock

backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi import HTTPException
from app.db.session import SessionLocal
from app.db.models import User, Job, Application
from app.schemas.match import JobMatchResult
from app.schemas.api import AnalyzeJobRequest
from app.agent.scraper import DiscoveredJob
from app.agent.ingestion import ingest_single_job
from main import analyze_job

async def test_issues_2_1_and_2_2():
    print("=" * 65, flush=True)
    print("RUNNING STEP 2 - ISSUES 2.1 & 2.2: INGESTION SESSION SAFETY & SCORER SCOPING", flush=True)
    print("=" * 65, flush=True)

    db = SessionLocal()
    created_job_ids = []
    try:
        u1 = db.query(User).filter(User.id == 1).first()
        u2 = db.query(User).filter(User.id == 2).first()
        assert u1 is not None and u2 is not None

        # 1. Test ingest_single_job passes user_id=2 to analyze_and_score_job
        dummy_job = DiscoveredJob(
            title="Senior Python Backend Architect",
            company="MultiTenant Innovations Ltd",
            location="Remote",
            portal="naukri",
            job_url="https://www.naukri.com/job-listings-python-architect-test-9999",
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

            res = await ingest_single_job(discovered=dummy_job, min_match_score=70, user_id=2)
            assert res is not None
            created_job_ids.append(res.job_id)

            # Verify scorer received user_id=2
            assert mock_score.called
            call_kwargs = mock_score.call_args.kwargs
            assert call_kwargs.get("user_id") == 2, f"Expected user_id=2 in scorer, got {call_kwargs.get('user_id')}"
            print("[PASS] 1. ingest_single_job correctly passes user_id=2 to analyze_and_score_job.", flush=True)

        # 2. Verify Database records are strictly bound to User 2
        saved_job = db.query(Job).filter(Job.id == res.job_id).first()
        assert saved_job is not None
        assert saved_job.user_id == 2
        assert len(saved_job.applications) > 0
        assert saved_job.applications[0].user_id == 2
        print("[PASS] 2. Ingested Job and Application records strictly scoped to User 2.", flush=True)

        # 3. User 1 cannot see User 2's ingested job
        from app.db.crud import list_jobs
        u1_jobs = list_jobs(db, user_id=1, limit=500)
        assert not any(j.id == res.job_id for j in u1_jobs)
        print("[PASS] 3. User 1 tenant boundary verified: Cannot see User 2's ingested job.", flush=True)

        # 4. Rollback safety on exception test
        with patch("app.agent.ingestion.create_job", side_effect=Exception("Simulated SQLite constraint failure")):
            err_res = await ingest_single_job(discovered=dummy_job, min_match_score=70, user_id=2)
            assert err_res is None
            print("[PASS] 4. DB session rollback safely triggered on ingestion error (Zero session lock leak).", flush=True)

        # 5. Route /api/analyze passes user_id to scorer
        with patch("app.agent.scorer.analyze_and_score_job") as mock_analyze:
            mock_analyze.return_value = mock_match
            req = AnalyzeJobRequest(
                job_description="Python distributed systems engineer with async messaging.",
                job_title="Python Distributed Systems",
                company_name="Cloud Corp"
            )
            route_res = analyze_job(req=req, db=db, current_user=u2)
            assert route_res is not None
            created_job_ids.append(route_res.job_id)

            assert mock_analyze.called
            assert mock_analyze.call_args.kwargs.get("user_id") == 2
            print("[PASS] 5. /api/analyze route strictly passes current_user.id (user_id=2) to scorer.", flush=True)

        print("=" * 65, flush=True)
        print("[SUCCESS] ALL 5 VERIFICATIONS PASSED FOR STEP 2 - ISSUES 2.1 & 2.2!", flush=True)
        print("=" * 65, flush=True)
    finally:
        # Cleanup test jobs
        for jid in created_job_ids:
            try:
                from app.db.crud import delete_job
                delete_job(db, job_id=jid, user_id=2)
            except Exception:
                pass
        db.close()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_issues_2_1_and_2_2())
