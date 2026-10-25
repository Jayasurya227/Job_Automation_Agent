"""
Module: test_applier.py
Purpose: Step 4.2 Verification Suite - Tests Screening Q&A Memory Bank and Playwright Form Filler.
Standards: Rule 1 (Zero Blind Trust), Rule 2 (Type & Schema Validation), Rule 5 (Production Reliability).
"""
import os
import sys
import time
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.db.session import init_db
from app.agent.qa_bank import seed_default_qa_bank, get_or_generate_answer
from app.agent.applier import EasyApplyFiller, run_form_fill_pipeline

def run_applier_tests():
    init_db()
    print("\n=======================================================", flush=True)
    print("  STEP 4.2 FORM FILLER & Q&A MEMORY BANK TEST SUITE", flush=True)
    print("=======================================================", flush=True)

    # -------------------------------------------------------------
    # TEST 1: Q&A Memory Bank Seeding & Instant Lookup
    # -------------------------------------------------------------
    print("\n[TEST 1/4] Testing Screening Q&A Memory Bank Seeding & Retrieval...", flush=True)
    seeded_count = seed_default_qa_bank()
    assert seeded_count >= 0, "Seeding returned invalid count"

    # Test work authorization lookup
    auth_q = "Are you legally authorized to work in India?"
    auth_res = get_or_generate_answer(auth_q)
    assert auth_res["answer"] == "Yes", f"Expected 'Yes', got {auth_res['answer']}"
    assert auth_res["confidence"] >= 0.9, "Low confidence on cached answer"
    print(f"  [SUCCESS] Work Auth resolved: {auth_res['answer']} (Source: {auth_res['source']})", flush=True)

    # Test notice period lookup
    notice_q = "What is your current notice period?"
    notice_res = get_or_generate_answer(notice_q)
    assert "Immediate" in notice_res["answer"] or "0" in notice_res["answer"], f"Unexpected notice answer: {notice_res['answer']}"
    print(f"  [SUCCESS] Notice period resolved: {notice_res['answer']}", flush=True)

    # -------------------------------------------------------------
    # TEST 2: Rule-Based Skill & Experience Matching
    # -------------------------------------------------------------
    print("\n[TEST 2/4] Testing Profile Rule-Based Matching...", flush=True)
    exp_q = "How many years of Python experience do you have?"
    exp_res = get_or_generate_answer(exp_q, allow_ai_generation=False)
    assert exp_res["answer"] == "0.8", f"Expected '0.8', got {exp_res['answer']}"
    print(f"  [SUCCESS] Known skill experience: {exp_res['answer']} years", flush=True)

    unseen_skill_q = "How many years of Fortran experience do you have?"
    unseen_res = get_or_generate_answer(unseen_skill_q, allow_ai_generation=False)
    assert unseen_res["answer"] == "0", f"Expected '0', got {unseen_res['answer']}"
    print(f"  [SUCCESS] Unseen skill experience: {unseen_res['answer']} years", flush=True)

    # -------------------------------------------------------------
    # TEST 3: Multi-Step Playwright Form Auto-Fill (Assisted Mode)
    # -------------------------------------------------------------
    print("\n[TEST 3/4] Testing Multi-Step Easy Apply Form Filler (Assisted Mode)...", flush=True)
    mock_html = Path("data/mock_easy_apply.html").resolve()
    assert mock_html.exists(), f"Mock HTML file missing at {mock_html}"

    test_thread = f"test_assisted_{int(time.time() * 1000)}"
    filler = EasyApplyFiller(headless=True)
    
    stage_res = filler.fill_and_stage_application(
        target_url_or_path=str(mock_html),
        job_title="Junior AI Engineer",
        company_name="NextGen AI Labs",
        thread_id=test_thread,
        auto_submit=False  # Assisted mode: Stop at review screen
    )

    assert stage_res.status == "READY_FOR_REVIEW", f"Expected READY_FOR_REVIEW, got {stage_res.status}"
    assert stage_res.steps_traversed >= 2, f"Expected at least 2 steps traversed, got {stage_res.steps_traversed}"
    assert stage_res.snapshot_path is not None, "Missing review snapshot path"
    assert Path(stage_res.snapshot_path).exists(), f"Snapshot file not saved at {stage_res.snapshot_path}"
    assert stage_res.snapshot_path.endswith(".png"), "Snapshot file is not a PNG"

    # Verify filled fields
    filled_names = {f.field_type: f.value_filled for f in stage_res.filled_fields}
    assert "name" in filled_names or "first_name" in filled_names, "Name field was not populated"
    assert "email" in filled_names, "Email was not populated"
    assert "phone" in filled_names, "Phone was not populated"
    print(f"  [SUCCESS] Assisted Mode paused safely at Review Screen.")
    print(f"            Snapshot captured: {Path(stage_res.snapshot_path).name} ({Path(stage_res.snapshot_path).stat().st_size} bytes)")
    print(f"            Fields filled: {len(stage_res.filled_fields)} form controls")

    # -------------------------------------------------------------
    # TEST 4: Final Submission Flow Upon User Approval
    # -------------------------------------------------------------
    print("\n[TEST 4/4] Testing Final Application Submission Upon User Approval...", flush=True)
    submit_thread = f"test_submit_{int(time.time() * 1000)}"
    submit_res = filler.fill_and_stage_application(
        target_url_or_path=str(mock_html),
        job_title="Junior AI Engineer",
        company_name="NextGen AI Labs",
        thread_id=submit_thread,
        auto_submit=True  # User approved: click Submit application
    )

    assert submit_res.status == "SUBMITTED", f"Expected SUBMITTED, got {submit_res.status}"
    assert submit_res.confirmation_snapshot_path is not None, "Missing confirmation snapshot path"
    assert Path(submit_res.confirmation_snapshot_path).exists(), "Confirmation snapshot file not found"
    print(f"  [SUCCESS] Application submitted successfully.")
    print(f"            Confirmation Snapshot: {Path(submit_res.confirmation_snapshot_path).name} ({Path(submit_res.confirmation_snapshot_path).stat().st_size} bytes)")

    print("\n=======================================================")
    print("  STEP 4.2 FORM FILLER & Q&A BANK: ALL 4 TESTS PASSED (100%)")
    print("=======================================================\n", flush=True)

if __name__ == "__main__":
    run_applier_tests()
