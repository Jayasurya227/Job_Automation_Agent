import sys
import os
import asyncio
from pathlib import Path

# Force WindowsSelectorEventLoopPolicy to prevent IOCP hang on Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.db.session import SessionLocal
from app.db.models import User, Job
from app.agent.task_queue import MultiTenantTaskQueue, TaskStatus

async def async_main():
    print("==================================================================")
    print("STEP 3 - ISSUE 3.2 (BUG 16): TASK QUEUE WORKER POOL & RESILIENCE")
    print("==================================================================")

    db = SessionLocal()
    try:
        u1 = db.query(User).filter(User.id == 1).first()
        u2 = db.query(User).filter(User.id == 2).first()
        assert u1 is not None and u2 is not None
        u1_initial_jobs = db.query(Job).filter(Job.user_id == 1).count()

        # Initialize a test task queue with fast pacing for testing
        test_queue = MultiTenantTaskQueue(max_concurrent_workers=2)
        test_queue.rate_limiter.min_interval = 0.05  # fast for test suite
        test_queue.start()

        assert len(test_queue._workers) == 2, f"Expected 2 workers, got {len(test_queue._workers)}"
        print("  [PASS] Worker pool initialized with 2 concurrent workers.")

        # -------------------------------------------------------------
        # TEST 1: Concurrent task processing for User 1 and User 2
        # -------------------------------------------------------------
        print("\n--- Test 1: Multi-tenant Concurrent Execution ---")
        async def mock_task_u1(task):
            await asyncio.sleep(0.1)
            return {"user": 1, "processed": True}

        async def mock_task_u2(task):
            await asyncio.sleep(0.1)
            return {"user": 2, "processed": True}

        t1 = await test_queue.enqueue_task(user_id=1, task_type="custom", custom_coro_fn=mock_task_u1)
        t2 = await test_queue.enqueue_task(user_id=2, task_type="custom", custom_coro_fn=mock_task_u2)

        # Wait for both tasks to complete
        for _ in range(50):
            if t1.status == TaskStatus.COMPLETED and t2.status == TaskStatus.COMPLETED:
                break
            await asyncio.sleep(0.05)

        assert t1.status == TaskStatus.COMPLETED, f"t1 status: {t1.status}"
        assert t2.status == TaskStatus.COMPLETED, f"t2 status: {t2.status}"
        assert t1.result == {"user": 1, "processed": True}
        assert t2.result == {"user": 2, "processed": True}
        print("  [PASS] Concurrent tasks completed successfully with isolated results.")

        # -------------------------------------------------------------
        # TEST 2: Worker Resilience on Failure
        # -------------------------------------------------------------
        print("\n--- Test 2: Worker Resilience Against Task Exceptions ---")
        async def failing_task(task):
            raise ValueError("Deliberate failure in candidate task execution")

        t_fail = await test_queue.enqueue_task(user_id=2, task_type="custom", custom_coro_fn=failing_task)

        for _ in range(30):
            if t_fail.status == TaskStatus.FAILED:
                break
            await asyncio.sleep(0.05)

        assert t_fail.status == TaskStatus.FAILED, f"Expected FAILED, got {t_fail.status}"
        assert "Deliberate failure" in str(t_fail.error)
        print("  [PASS] Failing task correctly flagged as FAILED without unhandled crash.")

        # Ensure workers are STILL alive after failure!
        alive_workers = [w for w in test_queue._workers if not w.done()]
        assert len(alive_workers) == 2, f"FAIL: Workers died after exception! Alive: {len(alive_workers)}"

        # Enqueue another task to confirm queue still operational
        async def normal_task(task):
            return {"operational": True}

        t_subsequent = await test_queue.enqueue_task(user_id=1, task_type="custom", custom_coro_fn=normal_task)
        for _ in range(30):
            if t_subsequent.status == TaskStatus.COMPLETED:
                break
            await asyncio.sleep(0.05)

        assert t_subsequent.status == TaskStatus.COMPLETED
        print("  [PASS] Worker pool remained 100% operational after task failure.")

        # -------------------------------------------------------------
        # TEST 3: Graceful Queue Shutdown
        # -------------------------------------------------------------
        print("\n--- Test 3: Graceful Queue Shutdown ---")
        await test_queue.stop()
        assert not test_queue._is_running
        assert len(test_queue._workers) == 0
        print("  [PASS] Task queue stopped and drained cleanly.")

        # -------------------------------------------------------------
        # TEST 4: User 1 Zero Data Loss Verification
        # -------------------------------------------------------------
        print("\n--- Test 4: User 1 Zero Data Loss Verification ---")
        u1_final_jobs = db.query(Job).filter(Job.user_id == 1).count()
        assert u1_final_jobs == u1_initial_jobs, f"User 1 jobs altered from {u1_initial_jobs} to {u1_final_jobs}!"
        print(f"  [PASS] User 1 jobs intact: exactly {u1_final_jobs} jobs.")

        print("\n==================================================================")
        print("ALL CHECKS PASSED FOR STEP 3 - ISSUE 3.2 (BUG 16)!")
        print("==================================================================")

    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(async_main())
