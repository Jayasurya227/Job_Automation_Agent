import sys
import os
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Force WindowsSelectorEventLoopPolicy to prevent IOCP hang on Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.db.session import SessionLocal
from app.db.models import User, Job
from app.agent.scheduler import (
    get_now_ist,
    get_portal_timeline_slot,
    autopilot_scheduler,
    IST_TIMEZONE,
    OFFICE_START_HOUR,
    OFFICE_END_HOUR,
)

def run_tests():
    print("==================================================================")
    print("STEP 3 - ISSUE 3.3 (BUG 17): IST VS UTC TIMEZONE ALIGNMENT")
    print("==================================================================")

    db = SessionLocal()
    try:
        u1 = db.query(User).filter(User.id == 1).first()
        assert u1 is not None
        u1_initial_jobs = db.query(Job).filter(Job.user_id == 1).count()

        # -------------------------------------------------------------
        # TEST 1: IST Timezone definition & get_now_ist() offset
        # -------------------------------------------------------------
        print("\n--- Test 1: get_now_ist() Timezone & Offset ---")
        now_ist = get_now_ist()
        assert now_ist.tzinfo is not None, "get_now_ist() must be timezone-aware"
        offset = now_ist.utcoffset()
        assert offset == timedelta(hours=5, minutes=30), f"Expected UTC+05:30, got {offset}"
        print(f"  [PASS] Current IST Time: {now_ist.strftime('%Y-%m-%d %H:%M:%S %Z')} (Offset: +05:30)")

        # -------------------------------------------------------------
        # TEST 2: UTC Server Time Conversion to IST Timetable
        # -------------------------------------------------------------
        print("\n--- Test 2: Simulating UTC Cloud Server Clock -> IST Conversion ---")
        
        # Simulation A: 03:30 AM UTC = 09:00 AM IST (Office Hours Start, Work Slot 1)
        utc_morning = datetime(2026, 11, 19, 3, 30, 0, tzinfo=timezone.utc)
        slot_a = get_portal_timeline_slot(dt=utc_morning)
        assert slot_a["is_office_hours"] is True, "03:30 UTC (09:00 IST) must be office hours"
        assert slot_a["phase"] == "work", f"Expected work phase, got {slot_a['phase']}"
        assert slot_a["slot_id"] == 1, f"Expected slot_id 1, got {slot_a['slot_id']}"
        print(f"  [PASS] 03:30 UTC correctly resolved to 09:00 IST Work Slot 1 ({slot_a['slot_label']})")

        # Simulation B: 04:35 AM UTC = 10:05 AM IST (Rest Break 1)
        utc_break = datetime(2026, 11, 19, 4, 35, 0, tzinfo=timezone.utc)
        slot_b = get_portal_timeline_slot(dt=utc_break)
        assert slot_b["is_office_hours"] is True
        assert slot_b["phase"] == "break", f"Expected break phase, got {slot_b['phase']}"
        assert slot_b["slot_id"] == 1
        print(f"  [PASS] 04:35 UTC correctly resolved to 10:05 IST Rest Break 1 ({slot_b['slot_label']})")

        # Simulation C: 15:30 PM UTC = 21:00 PM IST (Office Hours Ended / 9:00 PM Sharp Cutoff)
        utc_closed = datetime(2026, 11, 19, 15, 30, 0, tzinfo=timezone.utc)
        slot_c = get_portal_timeline_slot(dt=utc_closed)
        assert slot_c["is_office_hours"] is False, "15:30 UTC (21:00 IST) must be closed"
        assert slot_c["phase"] == "closed", f"Expected closed phase, got {slot_c['phase']}"
        print(f"  [PASS] 15:30 UTC correctly resolved to 21:00 IST (Office Hours Closed: {slot_c['status_message']})")

        # Simulation D: 02:00 AM UTC = 07:30 AM IST (Before Office Hours)
        utc_early = datetime(2026, 11, 19, 2, 0, 0, tzinfo=timezone.utc)
        slot_d = get_portal_timeline_slot(dt=utc_early)
        assert slot_d["is_office_hours"] is False
        assert slot_d["phase"] == "closed"
        print(f"  [PASS] 02:00 UTC correctly resolved to 07:30 IST Night Standby")

        # -------------------------------------------------------------
        # TEST 3: Scheduler Status reflects IST timeline
        # -------------------------------------------------------------
        print("\n--- Test 3: Scheduler get_status() with IST Alignment ---")
        status = autopilot_scheduler.get_status(user_id=1)
        assert "timeline" in status
        assert status["timeline"]["active_window"] == "9:00 AM – 9:00 PM IST"
        print(f"  [PASS] Scheduler status correctly returned with IST timeline for User 1.")

        # -------------------------------------------------------------
        # TEST 4: User 1 Zero Data Loss Verification
        # -------------------------------------------------------------
        print("\n--- Test 4: User 1 Zero Data Loss Verification ---")
        u1_final_jobs = db.query(Job).filter(Job.user_id == 1).count()
        assert u1_final_jobs == u1_initial_jobs, f"User 1 jobs altered from {u1_initial_jobs} to {u1_final_jobs}!"
        print(f"  [PASS] User 1 jobs intact: exactly {u1_final_jobs} jobs.")

        print("\n==================================================================")
        print("ALL CHECKS PASSED FOR STEP 3 - ISSUE 3.3 (BUG 17)!")
        print("==================================================================")

    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
