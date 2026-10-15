"""
Module: test_hitl_gateway.py
Purpose: Sub-Phase 4.3 End-to-End Verification Suite for Human-in-the-Loop Review Gateway.
Standards: Rule 1 (Zero Blind Trust), Rule 2 (Type & Schema Safety), Rule 4 (Assisted Mode Review Gateway),
           Rule 5 (Production Reliability & Visual Confirmation).
"""
import sys
import time
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.db.session import init_db, SessionLocal
from app.db import crud
from app.agent.workflow import run_application_workflow, resume_application_workflow, get_sqlite_checkpointer

def run_hitl_gateway_tests():
    init_db()
    print("\n=======================================================", flush=True)
    print("  STEP 4.3 HUMAN-IN-THE-LOOP REVIEW GATEWAY TEST SUITE", flush=True)
    print("=======================================================", flush=True)

    mock_html = Path("data/mock_easy_apply.html").resolve()
    assert mock_html.exists(), "Mock HTML portal missing"

    # Create test job in SQLite DB
    with SessionLocal() as db:
        test_job = crud.create_job(
            db=db,
            job_title="Junior AI Engineer",
            company_name="NextGen AI Labs",
            location="Remote",
            portal_name="LinkedIn Easy Apply",
            job_url=str(mock_html),
            job_description="Python, FastAPI, LLMs, LangGraph, Playwright, SQLite."
        )
        job_id = test_job.id

    thread_id = f"hitl_test_{int(time.time() * 1000)}"
    print(f"\n[TEST 1/2] Initiating Assisted Application Workflow for Job #{job_id}...", flush=True)

    # 1. Start Assisted Workflow with mock HTML application URL
    stage_res = run_application_workflow(
        job_title="Junior AI Engineer",
        company_name="NextGen AI Labs",
        job_description="Python, FastAPI, LLMs, LangGraph, Playwright, SQLite.",
        job_url=str(mock_html),
        portal_name="LinkedIn Easy Apply",
        job_id=job_id,
        match_score=94,
        requires_human_approval=True,
        thread_id=thread_id,
        tailored_resume_tex_path="output/resumes/junior_ai_engineer_resume.tex",
        cold_email_body="Dear Hiring Team, I am eager to contribute to NextGen AI Labs.",
    )

    # 2. Assert workflow paused at Human Review Gateway
    assert stage_res["is_interrupted"] is True, "Assisted workflow failed to pause at Human Review Gateway"
    payload = stage_res["interrupt_payload"]
    assert payload is not None, "Missing interrupt payload"
    assert payload["job_title"] == "Junior AI Engineer", f"Unexpected job title: {payload.get('job_title')}"
    assert payload["match_score"] == 94, "Match score mismatch"
    assert payload.get("review_snapshot_path") is not None, "Review visual snapshot was not captured"
    
    snapshot_file = Path(payload["review_snapshot_path"])
    assert snapshot_file.exists(), f"Snapshot file not on disk: {snapshot_file}"
    assert snapshot_file.stat().st_size > 5000, f"Snapshot file seems corrupted: {snapshot_file.stat().st_size} bytes"

    print(f"  [SUCCESS] Workflow safely paused at Human Review Gateway.")
    print(f"            Visual Review Snapshot: {snapshot_file.name} ({snapshot_file.stat().st_size} bytes)")
    print(f"            Candidate Answers Staged: {len(payload.get('screening_answers', {}))} fields")

    # 3. Simulate Candidate Approving Application in Review Gateway
    print(f"\n[TEST 2/2] Resuming Interrupted Workflow Upon Candidate Approval...", flush=True)
    resumed = resume_application_workflow(
        thread_id=thread_id,
        approved=True
    )

    assert resumed["status"] == "SUBMITTED", f"Expected SUBMITTED status, got {resumed.get('status')}"
    
    # Verify SQLite database was updated to Applied
    with SessionLocal() as db:
        app_record = db.query(crud.Application).filter(crud.Application.job_id == job_id).first()
        assert app_record is not None, "Application record not found in SQLite"
        assert app_record.status == "Applied", f"Expected Applied in database, got {app_record.status}"
        assert app_record.applied_at is not None, "Applied timestamp missing"

    print(f"  [SUCCESS] Application submitted and database updated to 'Applied'.")
    print(f"            Applied At: {app_record.applied_at}")
    print(f"            Final status: {resumed['status']}")

    print("\n=======================================================")
    print("  HUMAN-IN-THE-LOOP REVIEW GATEWAY: ALL TESTS PASSED (100%)")
    print("=======================================================\n", flush=True)

if __name__ == "__main__":
    run_hitl_gateway_tests()
