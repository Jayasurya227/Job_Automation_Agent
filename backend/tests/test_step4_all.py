import sys
import os
import asyncio
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

# Force WindowsSelectorEventLoopPolicy to prevent IOCP hang on Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.db.session import SessionLocal
from app.db.models import User, Job, ApplicationAnswer
from app.agent.qa_bank import (
    seed_default_qa_bank,
    get_answer_from_rules,
    generate_ai_screening_answer,
)
from app.agent.booster import (
    boost_naukri_profile,
    _user_booster_locks,
    _last_boost_timestamps,
)
from main import get_screening_qa_bank, save_screening_qa_item, SaveQARequest

def run_master_step4_tests():
    print("==================================================================")
    print("MASTER STEP 4 REGRESSION TEST SUITE (BUGS 19 TO 22)")
    print("==================================================================")

    db = SessionLocal()
    try:
        u1 = db.query(User).filter(User.id == 1).first()
        u2 = db.query(User).filter(User.id == 2).first()
        assert u1 is not None and u2 is not None
        u1_initial_jobs = db.query(Job).filter(Job.user_id == 1).count()
        print(f"Pre-flight: User 1 ({u1.email}) has {u1_initial_jobs} jobs. User 2 ({u2.email}) exists.")

        # -------------------------------------------------------------
        # BUG 19: Dynamic Candidate Profile Injection in AI Q&A Brain
        # -------------------------------------------------------------
        print("\n--- [Bug 19] Dynamic Candidate Profile Facts Injection ---")
        captured_system = {}
        def mock_claude_messages_create(**kwargs):
            captured_system["instruction"] = kwargs.get("system", "")
            mock_block = MagicMock(type="text", text="Yes")
            mock_resp = MagicMock(stop_reason="end_turn", content=[mock_block])
            return mock_resp

        with patch("app.agent.qa_bank.claude_client.messages.create", side_effect=mock_claude_messages_create):
            ans = generate_ai_screening_answer(
                question="Do you have experience leading Python teams?",
                job_title="Lead Python Developer",
                user_id=2,
            )
            assert ans["answer"] == "Yes"

        inst = captured_system.get("instruction", "")
        assert "Candidate Two" in inst, "Candidate Two identity must be injected into system instructions"
        assert "Rayavaram Jayasurya" not in inst, "Zero cross-tenant identity leak in AI prompt"
        print("  [PASS] Bug 19: AI Q&A prompt strictly uses dynamic candidate profile.")

        # -------------------------------------------------------------
        # BUG 20: Multi-Tenant Q&A Seeding and API Route Security
        # -------------------------------------------------------------
        print("\n--- [Bug 20] Multi-Tenant Q&A Seeding & API Scoping ---")
        db.query(ApplicationAnswer).filter(ApplicationAnswer.user_id == 2).delete()
        db.commit()

        u1_qa_before = db.query(ApplicationAnswer).filter(ApplicationAnswer.user_id == 1).count()
        seed_count = seed_default_qa_bank(user_id=2)
        assert seed_count > 0

        # Verify all seeded records strictly tagged with user_id=2
        u2_seeded = db.query(ApplicationAnswer).filter(ApplicationAnswer.user_id == 2).all()
        assert len(u2_seeded) == seed_count
        assert all(a.user_id == 2 for a in u2_seeded)

        # Verify User 1 Q&A records completely untouched
        u1_qa_after = db.query(ApplicationAnswer).filter(ApplicationAnswer.user_id == 1).count()
        assert u1_qa_after == u1_qa_before

        # API isolation check
        qa_u2 = get_screening_qa_bank(db=db, current_user=u2)
        assert len(qa_u2) == seed_count
        print("  [PASS] Bug 20: Q&A bank seeded and retrieved strictly scoped to user_id.")

        # -------------------------------------------------------------
        # BUG 21: Playwright Chrome -> Chromium Fallback Engine
        # -------------------------------------------------------------
        print("\n--- [Bug 21] Playwright Browser Fallback (Chrome -> Chromium) ---")
        attempted_channels = []
        def mock_launch(**kwargs):
            ch = kwargs.get("channel")
            attempted_channels.append(ch)
            if ch == "chrome":
                raise RuntimeError("Executable doesn't exist at C:\\Program Files\\Google\\Chrome\\chrome.exe")
            mock_context = MagicMock()
            mock_page = MagicMock()
            mock_file_input = MagicMock()
            mock_page.query_selector.return_value = mock_file_input
            mock_context.pages = [mock_page]
            return mock_context

        with patch("pathlib.Path.exists", return_value=True), \
             patch("app.core.user_storage.get_user_resume", return_value=Path("test_resume.pdf")), \
             patch("app.agent.booster.sync_playwright") as mock_pw:
            mock_pw_inst = MagicMock()
            mock_pw.return_value.__enter__.return_value = mock_pw_inst
            mock_pw_inst.chromium.launch_persistent_context.side_effect = mock_launch

            _last_boost_timestamps[1] = 0.0
            boost_res = boost_naukri_profile(user_id=1, bypass_cooldown=True)
            assert attempted_channels == ["chrome", None]
            assert boost_res["status"] == "success"
        print("  [PASS] Bug 21: Booster gracefully fell back from 'chrome' to Chromium.")

        # -------------------------------------------------------------
        # BUG 22: Booster Multi-User Locks & Cooldown
        # -------------------------------------------------------------
        print("\n--- [Bug 22] Booster Multi-User Locks & Rate-Limiting ---")
        lock1 = _user_booster_locks[1]
        lock2 = _user_booster_locks[2]
        assert lock1 is not lock2

        # Lock 1 acquired
        lock1.acquire(blocking=False)
        res_locked = boost_naukri_profile(user_id=1, bypass_cooldown=True)
        assert res_locked["status"] == "already_running"
        lock1.release()

        # Cooldown check
        _last_boost_timestamps[1] = time.time() - 30
        res_cool = boost_naukri_profile(user_id=1, bypass_cooldown=False)
        assert res_cool["status"] == "already_boosted"
        print("  [PASS] Bug 22: Per-user booster concurrency locks and debouncing verified.")

        # -------------------------------------------------------------
        # ZERO DATA LOSS VERIFICATION
        # -------------------------------------------------------------
        print("\n--- User 1 Zero Data Loss Verification ---")
        u1_final_jobs = db.query(Job).filter(Job.user_id == 1).count()
        assert u1_final_jobs == u1_initial_jobs, f"User 1 jobs altered from {u1_initial_jobs} to {u1_final_jobs}!"
        print(f"  [PASS] User 1 jobs intact: exactly {u1_final_jobs} jobs.")

        # Clean up User 2 test Q&A
        db.query(ApplicationAnswer).filter(ApplicationAnswer.user_id == 2).delete()
        db.commit()

        print("\n==================================================================")
        print("MASTER STEP 4 REGRESSION SUITE: ALL 4 BUGS (19-22) 100% PASSED!")
        print("==================================================================")

    finally:
        db.close()

if __name__ == "__main__":
    run_master_step4_tests()
