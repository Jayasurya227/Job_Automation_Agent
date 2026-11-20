import sys
import os
import asyncio
from pathlib import Path

# Force WindowsSelectorEventLoopPolicy to prevent IOCP hang on Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from fastapi import HTTPException
from app.db.session import SessionLocal
from app.db.models import User, Job
from app.core.security import create_access_token
from app.agent.scheduler import autopilot_scheduler
from app.agent.task_queue import task_queue, TaskStatus
from app.core.user_storage import load_user_profile, save_user_profile
from main import (
    get_autopilot_status,
    trigger_autopilot_now,
    toggle_autopilot,
    get_user_tasks,
    cancel_user_task,
)

def run_tests():
    print("==================================================================")
    print("STEP 3 - ISSUE 3.1 (BUG 15): SCHEDULER & TASK QUEUE ISOLATION")
    print("==================================================================")

    db = SessionLocal()
    try:
        u1 = db.query(User).filter(User.id == 1).first()
        u2 = db.query(User).filter(User.id == 2).first()
        assert u1 is not None and u2 is not None, "Both User 1 and User 2 must exist"
        u1_initial_jobs = db.query(Job).filter(Job.user_id == 1).count()
        print(f"Pre-flight: User 1 ({u1.email}) has {u1_initial_jobs} jobs. User 2 ({u2.email}) exists.")

        user1_ctx = u1
        user2_ctx = u2

        # -------------------------------------------------------------
        # TEST 1: trigger_user_now() method exists and enqueues task
        # -------------------------------------------------------------
        print("\n--- Test 1: trigger_user_now() existence & task enqueue ---")
        assert hasattr(autopilot_scheduler, "trigger_user_now"), "FAIL: autopilot_scheduler missing trigger_user_now!"

        async def test_trigger():
            task_id = await autopilot_scheduler.trigger_user_now(user_id=2)
            assert task_id is not None and task_id.startswith("task_"), f"Invalid task_id: {task_id}"
            task = task_queue.get_task(task_id)
            assert task is not None, "Task must exist in task_queue"
            assert task.user_id == 2, f"Task user_id must be 2, got {task.user_id}"
            assert task.task_type == "autopilot_run", f"Task type must be autopilot_run, got {task.task_type}"
            return task_id

        t2_id = asyncio.run(test_trigger())
        print(f"  [PASS] trigger_user_now(user_id=2) enqueued task {t2_id} successfully.")

        # -------------------------------------------------------------
        # TEST 2: Task Queue Tenant Isolation (List Tasks)
        # -------------------------------------------------------------
        print("\n--- Test 2: Task Queue Isolation (User 1 vs User 2) ---")
        u1_tasks = get_user_tasks(current_user=user1_ctx)
        u2_tasks = get_user_tasks(current_user=user2_ctx)

        # Verify User 2 sees their task
        u2_task_ids = [t["task_id"] for t in u2_tasks]
        assert t2_id in u2_task_ids, "User 2 must see their own queued task"

        # Verify User 1 DOES NOT see User 2's task
        u1_task_ids = [t["task_id"] for t in u1_tasks]
        assert t2_id not in u1_task_ids, "FAIL: User 1 saw User 2's queued task! Tenant boundary breached!"
        print("  [PASS] Task listing is strictly isolated per tenant.")

        # -------------------------------------------------------------
        # TEST 3: Anti-Tamper Guard (User 1 cannot cancel User 2's task)
        # -------------------------------------------------------------
        print("\n--- Test 3: Anti-Tamper Guard on Task Cancellation ---")
        try:
            asyncio.run(cancel_user_task(task_id=t2_id, current_user=user1_ctx))
            assert False, "FAIL: User 1 should have been blocked from cancelling User 2's task!"
        except HTTPException as e:
            assert e.status_code == 403, f"Expected HTTP 403 Forbidden, got {e.status_code}"
            print(f"  [PASS] User 1 was strictly blocked with HTTP 403: {e.detail}")

        # User 2 cancels their own task
        cancel_res = asyncio.run(cancel_user_task(task_id=t2_id, current_user=user2_ctx))
        assert cancel_res["status"] == "cancelled", f"User 2 cancellation failed: {cancel_res}"
        print("  [PASS] User 2 successfully cancelled their own task.")

        # -------------------------------------------------------------
        # TEST 4: Toggle AutoPilot per-user isolation
        # -------------------------------------------------------------
        print("\n--- Test 4: Toggle AutoPilot Isolation ---")
        p1_before = load_user_profile(1)
        u1_enabled_before = getattr(p1_before.preferences, "autopilot_enabled", False)

        # Toggle for User 2
        toggle_res = toggle_autopilot(current_user=user2_ctx)
        assert toggle_res["user_id"] == 2, f"Toggle result should report user_id=2, got {toggle_res['user_id']}"

        # Verify User 1's profile was completely unaffected
        p1_after = load_user_profile(1)
        assert getattr(p1_after.preferences, "autopilot_enabled", False) == u1_enabled_before, \
            "FAIL: Toggling User 2 changed User 1's autopilot setting!"
        print("  [PASS] Toggle AutoPilot strictly modifies only the target user's profile.")

        # -------------------------------------------------------------
        # TEST 5: User 1 Zero Data Loss Verification
        # -------------------------------------------------------------
        print("\n--- Test 5: User 1 Zero Data Loss Verification ---")
        u1_final_jobs = db.query(Job).filter(Job.user_id == 1).count()
        assert u1_final_jobs == u1_initial_jobs, f"FAIL: User 1 jobs altered from {u1_initial_jobs} to {u1_final_jobs}!"
        print(f"  [PASS] User 1 jobs intact: exactly {u1_final_jobs} jobs.")

        print("\n==================================================================")
        print("ALL 5 CHECKS PASSED FOR STEP 3 - ISSUE 3.1 (BUG 15)!")
        print("==================================================================")

    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
