import sys
import os
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
from starlette.requests import Request
from fastapi import HTTPException

# Force WindowsSelectorEventLoopPolicy to prevent IOCP hang on Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.db.session import SessionLocal
from app.db.models import User, Job
from app.core.security import create_access_token
from app.core.user_storage import load_user_profile
from app.agent.scheduler import (
    autopilot_scheduler,
    get_now_ist,
    get_portal_timeline_slot,
)
from app.agent.task_queue import MultiTenantTaskQueue, task_queue, TaskStatus
from app.utils.event_bus import event_bus, emit_event
from main import (
    get_autopilot_status,
    trigger_autopilot_now,
    toggle_autopilot,
    get_user_tasks,
    cancel_user_task,
    stream_events,
)

def run_master_step3_tests():
    print("==================================================================")
    print("MASTER STEP 3 REGRESSION TEST SUITE (BUGS 15 TO 18)")
    print("==================================================================")

    db = SessionLocal()
    try:
        u1 = db.query(User).filter(User.id == 1).first()
        u2 = db.query(User).filter(User.id == 2).first()
        assert u1 is not None and u2 is not None
        u1_initial_jobs = db.query(Job).filter(Job.user_id == 1).count()
        print(f"Pre-flight: User 1 ({u1.email}) has {u1_initial_jobs} jobs. User 2 ({u2.email}) exists.")

        # -------------------------------------------------------------
        # BUG 15: Scheduler trigger_user_now & Task Queue Dispatch
        # -------------------------------------------------------------
        print("\n--- [Bug 15] AutoPilot trigger_user_now & Tenant Queue Isolation ---")
        async def check_trigger():
            task_id = await autopilot_scheduler.trigger_user_now(user_id=2)
            assert task_id.startswith("task_")
            t = task_queue.get_task(task_id)
            assert t.user_id == 2
            assert t.task_type == "autopilot_run"
            return task_id

        task_u2_id = asyncio.run(check_trigger())
        
        # User 2 sees task, User 1 cannot
        u1_tasks = get_user_tasks(current_user=u1)
        u2_tasks = get_user_tasks(current_user=u2)
        assert task_u2_id in [t["task_id"] for t in u2_tasks]
        assert task_u2_id not in [t["task_id"] for t in u1_tasks]

        # User 1 cannot cancel User 2's task
        try:
            asyncio.run(cancel_user_task(task_id=task_u2_id, current_user=u1))
            assert False, "User 1 should not cancel User 2 task"
        except HTTPException as e:
            assert e.status_code == 403

        # User 2 cancels own task
        c_res = asyncio.run(cancel_user_task(task_id=task_u2_id, current_user=u2))
        assert c_res["status"] == "cancelled"
        print("  [PASS] Bug 15: trigger_user_now, task isolation, and 403 anti-tamper verified.")

        # -------------------------------------------------------------
        # BUG 16: Task Queue Worker Pool & Exception Resilience
        # -------------------------------------------------------------
        print("\n--- [Bug 16] Worker Pool Concurrency & Crash Resilience ---")
        async def test_worker_pool():
            test_q = MultiTenantTaskQueue(max_concurrent_workers=2)
            test_q.rate_limiter.min_interval = 0.05
            test_q.start()
            
            # Failing task for User 2
            async def failing(t):
                raise RuntimeError("Worker exception test")
            tf = await test_q.enqueue_task(user_id=2, task_type="custom", custom_coro_fn=failing)
            for _ in range(25):
                if tf.status == TaskStatus.FAILED:
                    break
                await asyncio.sleep(0.05)
            assert tf.status == TaskStatus.FAILED

            # Verify workers survived
            alive = [w for w in test_q._workers if not w.done()]
            assert len(alive) == 2, "Workers must survive task exceptions"

            # Subsequent task for User 1 runs successfully
            async def normal(t):
                return {"success": True}
            tn = await test_q.enqueue_task(user_id=1, task_type="custom", custom_coro_fn=normal)
            for _ in range(25):
                if tn.status == TaskStatus.COMPLETED:
                    break
                await asyncio.sleep(0.05)
            assert tn.status == TaskStatus.COMPLETED
            await test_q.stop()

        asyncio.run(test_worker_pool())
        print("  [PASS] Bug 16: Worker pool resilient against exceptions, queue operational.")

        # -------------------------------------------------------------
        # BUG 17: IST vs UTC Timezone Normalization
        # -------------------------------------------------------------
        print("\n--- [Bug 17] IST vs UTC Timetable Normalization ---")
        now_ist = get_now_ist()
        assert now_ist.utcoffset() == timedelta(hours=5, minutes=30)
        
        # 03:30 UTC = 09:00 IST (Office open)
        utc_9am = datetime(2026, 11, 19, 3, 30, 0, tzinfo=timezone.utc)
        s9 = get_portal_timeline_slot(dt=utc_9am)
        assert s9["is_office_hours"] is True and s9["phase"] == "work"

        # 15:30 UTC = 21:00 IST (Office closed)
        utc_9pm = datetime(2026, 11, 19, 15, 30, 0, tzinfo=timezone.utc)
        s9p = get_portal_timeline_slot(dt=utc_9pm)
        assert s9p["is_office_hours"] is False and s9p["phase"] == "closed"
        print("  [PASS] Bug 17: UTC server time properly normalized to Indian Standard Time (IST).")

        # -------------------------------------------------------------
        # BUG 18: SSE Stream Token Auth & Zero-Leakage Channel Isolation
        # -------------------------------------------------------------
        print("\n--- [Bug 18] SSE Security & Private Channel Anti-Leakage ---")
        token_u1 = create_access_token(user_id=1, email=u1.email)
        token_u2 = create_access_token(user_id=2, email=u2.email)

        def make_req(auth_header=""):
            scope = {
                "type": "http", "method": "GET",
                "headers": [(b"authorization", auth_header.encode())] if auth_header else [],
            }
            return Request(scope)

        # 1. Unauthenticated blocked with 401
        res_anon = asyncio.run(stream_events(request=make_req(), topic="discovery:2"))
        assert res_anon.status_code == 401

        # 2. Cross-user blocked with 403
        res_cross = asyncio.run(stream_events(request=make_req(f"Bearer {token_u1}"), topic="discovery:2"))
        assert res_cross.status_code == 403

        # 3. Authorized access allowed (200)
        res_auth = asyncio.run(stream_events(request=make_req(f"Bearer {token_u2}"), topic="discovery:2"))
        assert res_auth.status_code == 200

        # 4. Zero Leakage to 'all'
        secret_marker = "secret_step3_regression_marker_999"
        emit_event("discovery:2", "test_step3", {"data": secret_marker})
        all_events = event_bus.get_recent_events("all")
        assert not any(secret_marker in str(e) for e in all_events), "Private event must not leak to 'all' channel"
        print("  [PASS] Bug 18: SSE private channels strictly protected, zero leakage to 'all'.")

        # -------------------------------------------------------------
        # ZERO DATA LOSS VERIFICATION
        # -------------------------------------------------------------
        print("\n--- User 1 Zero Data Loss Verification ---")
        u1_final_jobs = db.query(Job).filter(Job.user_id == 1).count()
        assert u1_final_jobs == u1_initial_jobs, f"User 1 jobs altered from {u1_initial_jobs} to {u1_final_jobs}!"
        print(f"  [PASS] User 1 jobs intact: exactly {u1_final_jobs} jobs.")

        print("\n==================================================================")
        print("MASTER STEP 3 REGRESSION SUITE: ALL 4 BUGS (15-18) 100% PASSED!")
        print("==================================================================")

    finally:
        db.close()

if __name__ == "__main__":
    run_master_step3_tests()
