"""
Test Suite: Step 1 - Issues 1.4 & 1.5 Verification
Focus: Workflow Apply and Resume Endpoints Auth, User Scoping, and Anti-Hijacking Guard.
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
from app.db.models import User, Job
from app.schemas.api import ApplyWorkflowRequest, ResumeWorkflowRequest
from app.agent.workflow import WORKFLOW_SESSIONS
from main import trigger_apply_workflow, resume_apply_workflow

async def test_issues_1_4_and_1_5():
    print("=" * 65, flush=True)
    print("RUNNING STEP 1 - ISSUES 1.4 & 1.5: WORKFLOW USER_ID SCOPING & ANTI-HIJACK", flush=True)
    print("=" * 65, flush=True)

    db = SessionLocal()
    try:
        u1 = db.query(User).filter(User.id == 1).first()
        u2 = db.query(User).filter(User.id == 2).first()
        assert u1 is not None and u2 is not None

        # Pick a job belonging to User 1
        u1_job = db.query(Job).filter(Job.user_id == 1).first()
        assert u1_job is not None, "User 1 has no jobs in DB"

        # 1. User 2 cannot trigger apply workflow on User 1's job (404 isolation)
        req_u2_on_u1_job = ApplyWorkflowRequest(job_id=u1_job.id, mode="assisted", portal_name="naukri")
        try:
            await trigger_apply_workflow(req=req_u2_on_u1_job, db=db, current_user=u2)
            assert False, "FAIL: User 2 was able to access User 1's job!"
        except HTTPException as e:
            assert e.status_code == 404
            print("[PASS] 1. User 2 cannot access or apply to User 1's job (Job 404 Scoped Isolation).", flush=True)

        # 2. When User 1 applies to their own job, run_application_workflow receives user_id=1
        with patch("main.run_application_workflow") as mock_run_wf:
            mock_run_wf.return_value = {
                "thread_id": "test_wf_thread_u1",
                "state": {"status": "REVIEW_GATEWAY", "execution_logs": []},
                "is_interrupted": True,
                "interrupt_payload": {"action": "human_approval_required"}
            }
            req_u1 = ApplyWorkflowRequest(job_id=u1_job.id, mode="assisted", portal_name="naukri")
            res = await trigger_apply_workflow(req=req_u1, db=db, current_user=u1)
            assert mock_run_wf.called
            call_kwargs = mock_run_wf.call_args.kwargs
            assert call_kwargs.get("user_id") == 1, f"Expected user_id=1, got {call_kwargs.get('user_id')}"
            print("[PASS] 2. trigger_apply_workflow passes current_user.id (user_id=1) to run_application_workflow.", flush=True)

        # 3. Anti-Hijacking Guard: User 1 cannot resume or decide User 2's pending workflow
        WORKFLOW_SESSIONS["test_thread_user_2"] = {
            "thread_id": "test_thread_user_2",
            "user_id": 2,
            "status": "REVIEW_GATEWAY",
            "job_title": "Frontend Engineer",
            "company_name": "TechCorp",
            "execution_logs": []
        }

        try:
            resume_req = ResumeWorkflowRequest(approved=True)
            # User 1 attempts to resume User 2's workflow
            try:
                await resume_apply_workflow(thread_id="test_thread_user_2", req=resume_req, current_user=u1)
                assert False, "FAIL: User 1 was allowed to resume User 2's workflow thread!"
            except HTTPException as e:
                assert e.status_code == 403, f"Expected 403 Forbidden, got {e.status_code}"
                print("[PASS] 3. Anti-Hijacking Guard: User 1 blocked from resuming User 2's workflow (HTTP 403).", flush=True)

            # 4. User 2 CAN resume their own workflow
            with patch("main.resume_application_workflow") as mock_resume:
                mock_resume.return_value = {
                    "thread_id": "test_thread_user_2",
                    "status": "SUBMITTED",
                    "is_interrupted": False,
                    "state": {"status": "SUBMITTED"},
                    "execution_logs": ["Candidate APPROVED submission"]
                }
                res_u2 = await resume_apply_workflow(thread_id="test_thread_user_2", req=resume_req, current_user=u2)
                assert res_u2.status == "SUBMITTED"
                assert mock_resume.called
                assert mock_resume.call_args.kwargs.get("user_id") == 2
                print("[PASS] 4. User 2 successfully resumes their own application workflow (user_id=2).", flush=True)
        finally:
            WORKFLOW_SESSIONS.pop("test_thread_user_2", None)

        print("=" * 65, flush=True)
        print("[SUCCESS] ALL 4 VERIFICATIONS PASSED FOR STEP 1 - ISSUES 1.4 & 1.5!", flush=True)
        print("=" * 65, flush=True)
    finally:
        db.close()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_issues_1_4_and_1_5())
