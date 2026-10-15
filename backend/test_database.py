"""
Module: test_database.py
Purpose: Step 2.1 Verification Suite - Validates SQLite schema, CRUD operations, and ACID integrity.
Standards: Rule 1 (Zero Blind Trust - Rigorous Validation), Rule 2 (Type & Foreign Key Integrity).
"""
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.db.session import init_db, SessionLocal, engine
from app.db.models import Job, JobEvaluation, Application, ApplicationAnswer
from app.db import crud
from app.schemas.match import JobMatchResult

def run_database_tests():
    print("\n=======================================================")
    print("  STEP 2.1 DATABASE VERIFICATION SUITE (SQLite)")
    print("=======================================================")

    # 1. Initialize Tables
    print("\n[TEST 1/5] Initializing Database Schema...")
    init_db()
    db = SessionLocal()
    print("  [SUCCESS] All tables created successfully.")

    try:
        # 2. Test Job Creation
        print("\n[TEST 2/5] Testing Job Insertion...")
        job = crud.create_job(
            db=db,
            job_title="Junior AI Engineer",
            company_name="NextGen AI Labs",
            job_description="Seeking a Python AI Engineer with LLM, RAG, and FastAPI experience.",
            location="Hyderabad, India (Hybrid)",
            portal_name="LinkedIn",
            job_url="https://linkedin.com/jobs/view/123456",
            salary_range="6-10 LPA"
        )
        assert job.id is not None, "Job ID was not generated"
        print(f"  [SUCCESS] Created Job ID: {job.id} | {job.job_title} at {job.company_name}")

        # 3. Test Evaluation Attachment
        print("\n[TEST 3/5] Testing AI Evaluation Association...")
        fake_match = JobMatchResult(
            job_title="Junior AI Engineer",
            company_name="NextGen AI Labs",
            match_score=92,
            recommendation="Apply",
            matching_skills=["Python", "FastAPI", "LLMs", "RAG"],
            missing_skills=[],
            key_strengths=["Engineered Video RAG pipeline with FastAPI", "Built Playwright automation"],
            summary_reasoning="Strong alignment with candidate verified background in Video RAG and FastAPI."
        )
        eval_record = crud.save_job_evaluation(db=db, job_id=job.id, match=fake_match)
        assert eval_record.match_score == 92, "Match score mismatch"
        assert eval_record.job.company_name == "NextGen AI Labs", "Relationship traversal failed"
        print(f"  [SUCCESS] Attached Evaluation | Score: {eval_record.match_score}% | Rec: {eval_record.recommendation}")

        # 4. Test Application Tracking & Status Transitions
        print("\n[TEST 4/5] Testing Application Pipeline Tracking...")
        app_record = crud.create_or_update_application(
            db=db,
            job_id=job.id,
            status="Tailored",
            tex_path="output/resumes/junior_ai_engineer_resume.tex",
            cold_subject="AI Engineer: Video RAG & FastAPI Expertise",
            cold_body="Hi David, impressed by NextGen AI's work...",
            linkedin_note="Hi David, would love to connect regarding the AI Engineer role!"
        )
        assert app_record.status == "Tailored", "Initial status mismatch"
        print(f"  [SUCCESS] Created Application | Status: {app_record.status}")

        # Transition status to Applied
        updated_app = crud.update_application_status(db=db, application_id=app_record.id, new_status="Applied")
        assert updated_app.status == "Applied", "Status update failed"
        assert updated_app.applied_at is not None, "applied_at timestamp was not set"
        print(f"  [SUCCESS] Updated Status: {updated_app.status} | Timestamp: {updated_app.applied_at.isoformat()}")

        # 5. Test Q&A Screening Answers and Cascading Delete
        print("\n[TEST 5/5] Testing Q&A Storage & Cascading Deletion...")
        qa = crud.save_qa_answer(
            db=db,
            question="Are you an immediate joiner?",
            answer="Yes, 0 days notice period. Available to join immediately.",
            category="Notice Period"
        )
        assert qa.id is not None, "QA answer ID missing"
        qas = crud.list_qa_answers(db=db)
        assert len(qas) >= 1, "Failed to list QA answers"
        print(f"  [SUCCESS] Saved Q&A: '{qa.question}' -> '{qa.answer}'")

        # Test Cascading Deletion
        job_id_to_delete = job.id
        crud.delete_job(db=db, job_id=job_id_to_delete)
        # Verify job is gone
        assert crud.get_job(db=db, job_id=job_id_to_delete) is None, "Job was not deleted"
        # Verify evaluation is also gone (cascade)
        eval_check = db.query(JobEvaluation).filter(JobEvaluation.job_id == job_id_to_delete).first()
        assert eval_check is None, "Evaluation was not cascaded on delete"
        # Verify application is also gone (cascade)
        app_check = db.query(Application).filter(Application.job_id == job_id_to_delete).first()
        assert app_check is None, "Application was not cascaded on delete"
        print("  [SUCCESS] Cascading Delete Verified: Zero orphaned records left in database.")

        print("\n=======================================================")
        print("  STEP 2.1 DATABASE TESTS: ALL 5 PASSED CLEANLY (100%)")
        print("=======================================================\n")

    finally:
        db.close()

if __name__ == "__main__":
    run_database_tests()
