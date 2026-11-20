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
from app.db.models import User, Job, ApplicationAnswer
from app.db import crud
from app.agent.qa_bank import (
    seed_default_qa_bank,
    get_answer_from_rules,
    generate_ai_screening_answer,
)
from main import get_screening_qa_bank, save_screening_qa_item, SaveQARequest

def run_tests():
    print("==================================================================")
    print("STEP 4 (Issues 4.1 & 4.2 - Bugs 19 & 20): Q&A BANK ISOLATION")
    print("==================================================================")

    db = SessionLocal()
    try:
        u1 = db.query(User).filter(User.id == 1).first()
        u2 = db.query(User).filter(User.id == 2).first()
        assert u1 is not None and u2 is not None
        u1_initial_jobs = db.query(Job).filter(Job.user_id == 1).count()
        print(f"Pre-flight: User 1 ({u1.email}) has {u1_initial_jobs} jobs. User 2 ({u2.email}) exists.")

        # -------------------------------------------------------------
        # TEST 1: seed_default_qa_bank scoped strictly to user_id (Bug 20)
        # -------------------------------------------------------------
        print("\n--- Test 1: seed_default_qa_bank User Scoping ---")
        # Clear any prior test Q&A for User 2
        db.query(ApplicationAnswer).filter(ApplicationAnswer.user_id == 2).delete()
        db.commit()

        u1_qa_before = db.query(ApplicationAnswer).filter(ApplicationAnswer.user_id == 1).count()
        seed_count = seed_default_qa_bank(user_id=2)
        assert seed_count > 0, f"Expected seeded count > 0, got {seed_count}"

        # Verify all newly seeded answers have user_id=2
        u2_answers = db.query(ApplicationAnswer).filter(ApplicationAnswer.user_id == 2).all()
        assert len(u2_answers) == seed_count
        for a in u2_answers:
            assert a.user_id == 2, f"Expected user_id=2, got {a.user_id}"

        # Verify User 1 Q&A count is completely unchanged
        u1_qa_after = db.query(ApplicationAnswer).filter(ApplicationAnswer.user_id == 1).count()
        assert u1_qa_after == u1_qa_before, f"User 1 Q&A changed from {u1_qa_before} to {u1_qa_after}!"
        print(f"  [PASS] Successfully seeded {seed_count} questions for User 2. User 1 records untouched ({u1_qa_after}).")

        # -------------------------------------------------------------
        # TEST 2: Dynamic Candidate Facts Injection in Claude Prompt (Bug 19)
        # -------------------------------------------------------------
        print("\n--- Test 2: Dynamic Profile Injection in AI Q&A Prompt ---")
        captured_system_instruction = {}

        def mock_claude_messages_create(**kwargs):
            captured_system_instruction["instruction"] = kwargs.get("system", "")
            mock_block = MagicMock()
            mock_block.type = "text"
            mock_block.text = "Yes"
            mock_resp = MagicMock()
            mock_resp.stop_reason = "end_turn"
            mock_resp.content = [mock_block]
            return mock_resp

        with patch("app.agent.qa_bank.claude_client.messages.create", side_effect=mock_claude_messages_create):
            # Generate answer for User 2
            ans_res = generate_ai_screening_answer(
                question="Are you comfortable working with React and TypeScript?",
                job_title="Senior Frontend Engineer",
                user_id=2,
            )
            assert ans_res["answer"] == "Yes"

        inst = captured_system_instruction.get("instruction", "")
        assert "Candidate Two" in inst, f"FAIL: Expected 'Candidate Two' in prompt instruction, got: {inst[:200]}"
        assert "Rayavaram Jayasurya" not in inst, f"FAIL: Leak! 'Rayavaram Jayasurya' appeared in User 2's AI prompt!"
        print("  [PASS] AI system prompt dynamically injected User 2's identity with zero cross-contamination.")

        # -------------------------------------------------------------
        # TEST 3: Dynamic Rule Patterns (Demographics & Rules)
        # -------------------------------------------------------------
        print("\n--- Test 3: Rule Pattern Scoping ---")
        rule_res = get_answer_from_rules("What is your current location?", user_id=2)
        assert rule_res is not None
        assert rule_res["category"] == "Location"
        print(f"  [PASS] Rule pattern accurately resolved candidate location: {rule_res['answer']}.")

        # -------------------------------------------------------------
        # TEST 4: API Endpoint Isolation
        # -------------------------------------------------------------
        print("\n--- Test 4: API Route get_screening_qa_bank Isolation ---")
        items_u2 = get_screening_qa_bank(db=db, current_user=u2)
        assert len(items_u2) > 0
        
        # Save a new custom item for User 2
        req = SaveQARequest(question="What is your preferred database?", answer="PostgreSQL and MongoDB", category="Technical")
        saved = save_screening_qa_item(req=req, db=db, current_user=u2)
        assert saved.question == "What is your preferred database?"

        # Verify saved item belongs to User 2 in DB
        db_rec = db.query(ApplicationAnswer).filter(ApplicationAnswer.id == saved.id).first()
        assert db_rec.user_id == 2, f"Expected user_id=2, got {db_rec.user_id}"

        # User 1 listing does NOT include User 2's new question
        items_u1 = get_screening_qa_bank(db=db, current_user=u1)
        u1_questions = [it.question for it in items_u1]
        assert "What is your preferred database?" not in u1_questions
        print("  [PASS] API endpoints strictly isolate Q&A banks per tenant.")

        # -------------------------------------------------------------
        # TEST 5: User 1 Zero Data Loss Verification
        # -------------------------------------------------------------
        print("\n--- Test 5: User 1 Zero Data Loss Verification ---")
        u1_final_jobs = db.query(Job).filter(Job.user_id == 1).count()
        assert u1_final_jobs == u1_initial_jobs, f"User 1 jobs altered from {u1_initial_jobs} to {u1_final_jobs}!"
        print(f"  [PASS] User 1 jobs intact: exactly {u1_final_jobs} jobs.")

        # Clean up User 2 test Q&A
        db.query(ApplicationAnswer).filter(ApplicationAnswer.user_id == 2).delete()
        db.commit()

        print("\n==================================================================")
        print("ALL 5 CHECKS PASSED FOR STEP 4 (ISSUES 4.1 & 4.2)!")
        print("==================================================================")

    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
