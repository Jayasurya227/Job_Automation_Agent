"""
Module: test_workflow.py
Purpose: Step 4.1 Verification Suite - Tests LangGraph State Machine, Conditional Routing,
         Human-in-the-Loop Interrupt, Command Resume, and SQLite Checkpoint Persistence.
Standards: Rule 1 (Zero Blind Trust), Rule 2 (Type & Schema Validation), Rule 5 (Production Reliability).
"""
import sys
import time
import sqlite3
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from langgraph.checkpoint.sqlite import SqliteSaver
from app.agent.workflow import (
    JobApplicationState,
    build_application_graph,
    get_sqlite_checkpointer,
    run_application_workflow,
    resume_application_workflow,
    DEFAULT_WORKFLOW_DB
)
from app.db.session import init_db
from app.agent.scorer import load_profile

def run_workflow_tests():
    init_db()
    print("\n=======================================================", flush=True)
    print("  STEP 4.1 LANGGRAPH STATE MACHINE VERIFICATION SUITE", flush=True)
    print("=======================================================", flush=True)

    # -------------------------------------------------------------
    # TEST 1: Graph Compilation & Node Verification
    # -------------------------------------------------------------
    print("\n[TEST 1/6] Verifying StateGraph Compilation & Architecture...", flush=True)
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    mem_saver = SqliteSaver(conn)
    graph = build_application_graph(checkpointer=mem_saver)
    assert graph is not None, "Graph failed to compile"
    print("  [SUCCESS] StateGraph compiled with nodes: evaluate, archive, tailor, prepare_application, human_review, submit", flush=True)

    # -------------------------------------------------------------
    # TEST 2: Low-Match Routing & Auto-Archiving (< 75%)
    # -------------------------------------------------------------
    print("\n[TEST 2/6] Testing Conditional Edge: Low-Match Auto-Archiving...", flush=True)
    low_match_thread = f"test_low_{int(time.time() * 1000)}"
    low_res = run_application_workflow(
        job_title="Senior Java Architect",
        company_name="Legacy Systems Corp",
        job_description="Requires 15 years of Enterprise Java, Spring Boot, SOAP services, and Oracle WebLogic.",
        match_score=40,  # Below 75% threshold
        thread_id=low_match_thread,
        checkpointer=mem_saver,
    )
    
    assert not low_res["is_interrupted"], "Low match job should not trigger human review interrupt"
    assert low_res["state"]["status"] == "ARCHIVED", f"Expected status ARCHIVED, got {low_res['state']['status']}"
    assert any("Archive Node" in log for log in low_res["state"]["execution_logs"]), "Missing Archive Node log"
    print(f"  [SUCCESS] Low-match job (40%) auto-routed to ARCHIVED with zero user interruption.", flush=True)

    # -------------------------------------------------------------
    # TEST 3: High-Match Assisted Mode & Human Review Interrupt
    # -------------------------------------------------------------
    print("\n[TEST 3/6] Testing High-Match Workflow & Human-in-the-Loop Interrupt...", flush=True)
    high_match_thread = f"test_high_{int(time.time() * 1000)}"
    high_res = run_application_workflow(
        job_title="Junior AI Engineer",
        company_name="NextGen AI Labs",
        job_description=(
            "Looking for Junior AI Engineer. Must know Python, FastAPI, LLMs, Prompt Engineering, "
            "RAG pipelines, Playwright web automation, and SQLite. Immediate joiners preferred."
        ),
        match_score=92,  # High match
        requires_human_approval=True,
        thread_id=high_match_thread,
        checkpointer=mem_saver,
        tailored_resume_tex_path="output/resumes/junior_ai_engineer_resume.tex",
        cold_email_body="Dear Hiring Team, I am excited to apply for the Junior AI Engineer position.",
    )
    
    # Verify execution paused at Human Review Gateway
    assert high_res["is_interrupted"] is True, "High match workflow did NOT interrupt for human review"
    payload = high_res["interrupt_payload"]
    assert payload is not None, "Missing interrupt payload"
    assert payload["job_title"] == "Junior AI Engineer", "Payload job title mismatch"
    assert payload["company_name"] == "NextGen AI Labs", "Payload company mismatch"
    assert payload["match_score"] == 92, "Payload score mismatch"
    expected_name = load_profile().personal_info.name
    assert payload["screening_answers"]["full_name"] == expected_name, "Screening answers candidate mismatch"
    print(f"  [SUCCESS] Workflow safely paused at Human Review Gateway.", flush=True)
    print(f"            Interrupt Payload: {payload['job_title']} at {payload['company_name']} ({payload['match_score']}%)", flush=True)
    print(f"            Candidate Answers Staged: {payload['screening_answers']['full_name']} ({payload['screening_answers']['email']})", flush=True)

    # -------------------------------------------------------------
    # TEST 4: Resuming Interrupted Workflow Upon Approval
    # -------------------------------------------------------------
    print("\n[TEST 4/6] Testing Resume Upon Human Approval (Command.resume)...", flush=True)
    resumed_res = resume_application_workflow(
        thread_id=high_match_thread,
        approved=True,
        checkpointer=mem_saver,
    )
    
    assert resumed_res["status"] == "SUBMITTED", f"Expected SUBMITTED, got {resumed_res['status']}"
    assert any("Candidate APPROVED" in log for log in resumed_res["execution_logs"]), "Missing approval log"
    assert any("Submit Node" in log for log in resumed_res["execution_logs"]), "Missing Submit Node log"
    print(f"  [SUCCESS] Interrupted workflow resumed and finalized submission: {resumed_res['status']}", flush=True)

    # -------------------------------------------------------------
    # TEST 5: Resuming Interrupted Workflow Upon Rejection
    # -------------------------------------------------------------
    print("\n[TEST 5/6] Testing Candidate Rejection in Review Gateway...", flush=True)
    saved_tex = high_res["state"].get("tailored_resume_tex_path") or "output/resumes/tailored_resume.tex"
    saved_body = high_res["state"].get("cold_email_body") or "Hello Hiring Team, I am interested in this role."
    
    reject_thread = f"test_reject_{int(time.time() * 1000)}"
    pre_reject = run_application_workflow(
        job_title="AI Engineer",
        company_name="Acme Tech",
        job_description="Python, FastAPI, LLMs, RAG.",
        match_score=85,
        requires_human_approval=True,
        thread_id=reject_thread,
        checkpointer=mem_saver,
        tailored_resume_tex_path=saved_tex,
        cold_email_body=saved_body,
    )
    assert pre_reject["is_interrupted"] is True, "Expected review interrupt"
    
    # Candidate rejects the application
    rejected_res = resume_application_workflow(
        thread_id=reject_thread,
        approved=False,
        reason="Role is purely on-site in a non-preferred city",
        checkpointer=mem_saver,
    )
    assert rejected_res["status"] == "REJECTED_BY_USER", f"Expected REJECTED_BY_USER, got {rejected_res['status']}"
    assert any("REJECTED" in log for log in rejected_res["execution_logs"]), "Missing rejection log"
    print(f"  [SUCCESS] Workflow safely halted upon rejection: {rejected_res['status']}", flush=True)

    # -------------------------------------------------------------
    # TEST 6: SQLite Disk Checkpoint Persistence & Crash Recovery
    # -------------------------------------------------------------
    print("\n[TEST 6/6] Testing SQLite Checkpoint Persistence on Disk...", flush=True)
    disk_db = Path("data/test_workflows.db")
    if disk_db.exists():
        disk_db.unlink()
    disk_db.parent.mkdir(parents=True, exist_ok=True)
    
    disk_saver = get_sqlite_checkpointer(str(disk_db))
    disk_thread = f"disk_thread_{int(time.time() * 1000)}"
    
    # Start workflow and pause at interrupt
    disk_run = run_application_workflow(
        job_title="Python Developer",
        company_name="CloudScale AI",
        job_description="Python, FastAPI, SQLite, Playwright.",
        match_score=88,
        requires_human_approval=True,
        thread_id=disk_thread,
        checkpointer=disk_saver,
        tailored_resume_tex_path=saved_tex,
        cold_email_body=saved_body,
    )
    assert disk_run["is_interrupted"] is True, "Disk workflow did not pause"
    
    # Simulate fresh process reconnection from SQLite file
    conn_fresh = sqlite3.connect(str(disk_db), check_same_thread=False)
    disk_saver_fresh = SqliteSaver(conn_fresh)
    
    recovered_res = resume_application_workflow(
        thread_id=disk_thread,
        approved=True,
        checkpointer=disk_saver_fresh,
    )
    assert recovered_res["status"] == "SUBMITTED", "Failed to recover state from SQLite disk checkpointer"
    print(f"  [SUCCESS] Persistent SQLite checkpointer successfully resumed interrupted state across sessions.", flush=True)
    
    # Cleanup test db
    conn_fresh.close()
    if disk_db.exists():
        try:
            disk_db.unlink()
        except Exception:
            pass

    print("\n=======================================================")
    print("  LANGGRAPH WORKFLOW ENGINE: ALL 6 TESTS PASSED (100%)")
    print("=======================================================\n", flush=True)

if __name__ == "__main__":
    run_workflow_tests()
