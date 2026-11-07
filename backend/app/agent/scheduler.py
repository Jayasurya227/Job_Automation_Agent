"""
Module: scheduler.py
Purpose: Dynamic Office Hours Auto-Pilot Background Scheduler for Autonomous Job Agent.
         Active Window: 9:00 AM – 9:00 PM (09:00 – 21:00).
         - Triggers an immediate search as soon as Auto-Pilot is turned ON during office hours.
         - Automatically shuts OFF at 9:00 PM sharp.
         - Periodically searches during office hours.
Standards: Rule 1 (Zero Blind Trust), Rule 2 (Type & Schema Safety), Rule 5 (Production Reliability).
"""
import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from app.config import READY_MATCH_THRESHOLD, AUTOPILOT_AUTO_SUBMIT, BASE_DIR
from app.agent.scorer import load_profile
from app.agent.ingestion import discover_and_ingest
from app.utils.event_bus import emit_event

logger = logging.getLogger("agent.scheduler")

OFFICE_START_HOUR = 9   # 9:00 AM
OFFICE_END_HOUR = 21    # 9:00 PM (21:00)

TIMETABLE_SLOTS = [
    {"start": 540, "end": 600, "phase": "work", "slot_id": 1, "time_label": "09:00 AM – 10:00 AM", "name": "Work Slot 1"},
    {"start": 600, "end": 630, "phase": "break", "slot_id": 1, "time_label": "10:00 AM – 10:30 AM", "name": "Rest Break 1"},
    {"start": 630, "end": 690, "phase": "work", "slot_id": 2, "time_label": "10:30 AM – 11:30 AM", "name": "Work Slot 2"},
    {"start": 690, "end": 720, "phase": "break", "slot_id": 2, "time_label": "11:30 AM – 12:00 PM", "name": "Rest Break 2"},
    {"start": 720, "end": 780, "phase": "work", "slot_id": 3, "time_label": "12:00 PM – 01:00 PM", "name": "Work Slot 3"},
    {"start": 780, "end": 810, "phase": "break", "slot_id": 3, "time_label": "01:00 PM – 01:30 PM", "name": "Rest Break 3"},
    {"start": 810, "end": 870, "phase": "work", "slot_id": 4, "time_label": "01:30 PM – 02:30 PM", "name": "Work Slot 4"},
    {"start": 870, "end": 900, "phase": "break", "slot_id": 4, "time_label": "02:30 PM – 03:00 PM", "name": "Rest Break 4"},
    {"start": 900, "end": 960, "phase": "work", "slot_id": 5, "time_label": "03:00 PM – 04:00 PM", "name": "Work Slot 5"},
    {"start": 960, "end": 990, "phase": "break", "slot_id": 5, "time_label": "04:00 PM – 04:30 PM", "name": "Rest Break 5"},
    {"start": 990, "end": 1050, "phase": "work", "slot_id": 6, "time_label": "04:30 PM – 05:30 PM", "name": "Work Slot 6"},
    {"start": 1050, "end": 1080, "phase": "break", "slot_id": 6, "time_label": "05:30 PM – 06:00 PM", "name": "Rest Break 6"},
    {"start": 1080, "end": 1140, "phase": "work", "slot_id": 7, "time_label": "06:00 PM – 07:00 PM", "name": "Work Slot 7"},
    {"start": 1140, "end": 1170, "phase": "break", "slot_id": 7, "time_label": "07:00 PM – 07:30 PM", "name": "Rest Break 7"},
    {"start": 1170, "end": 1230, "phase": "work", "slot_id": 8, "time_label": "07:30 PM – 08:30 PM", "name": "Work Slot 8"},
    {"start": 1230, "end": 1260, "phase": "break", "slot_id": 8, "time_label": "08:30 PM – 09:00 PM", "name": "Rest Break 8"},
]


def get_portal_timeline_slot(dt: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Resolves the exact 1-Hour Work + 30-Minute Break timetable slot for Naukri.
    Active Office Window: 9:00 AM – 9:00 PM IST (09:00 to 21:00).
    Cycle:
       Slot 1: 09:00 – 10:00 (Work)  -> 10:00 – 10:30 (Rest Break)
       Slot 2: 10:30 – 11:30 (Work)  -> 11:30 – 12:00 (Rest Break)
       Slot 3: 12:00 – 01:00 (Work)  -> 01:00 – 01:30 (Rest Break)
       Slot 4: 01:30 – 02:30 (Work)  -> 02:30 – 03:00 (Rest Break)
       Slot 5: 03:00 – 04:00 (Work)  -> 04:00 – 04:30 (Rest Break)
       Slot 6: 04:30 – 05:30 (Work)  -> 05:30 – 06:00 (Rest Break)
       Slot 7: 06:00 – 07:00 (Work)  -> 07:00 – 07:30 (Rest Break)
       Slot 8: 07:30 – 08:30 (Work)  -> 08:30 – 09:00 (Rest Break)
       Night:  09:00 PM – 09:00 AM (Closed / Cooldown)
    """
    now = dt or datetime.now()
    current_minutes = now.hour * 60 + now.minute
    current_seconds = now.second

    if current_minutes < 540 or current_minutes >= 1260:
        is_office_hours = False
        phase = "closed"
        if current_minutes >= 1260:
            minutes_until_9am = (24 * 60 - current_minutes) + 540
        else:
            minutes_until_9am = 540 - current_minutes
        remaining_seconds = minutes_until_9am * 60 - current_seconds
        remaining_minutes = max(1, round(remaining_seconds / 60))
        status_message = "🌙 Office Hours Closed (Resumes tomorrow at 9:00 AM)"
        slot_label = "Night Cooldown (Closed)"
        next_event_label = "Work Slot 1 at 09:00 AM"
        active_slot_id = 0
    else:
        is_office_hours = True
        current_slot = None
        next_slot = None
        for idx, slot in enumerate(TIMETABLE_SLOTS):
            if slot["start"] <= current_minutes < slot["end"]:
                current_slot = slot
                next_slot = TIMETABLE_SLOTS[idx + 1] if idx + 1 < len(TIMETABLE_SLOTS) else None
                break

        if current_slot is None:
            current_slot = TIMETABLE_SLOTS[0]

        phase = current_slot["phase"]
        active_slot_id = current_slot["slot_id"]
        slot_label = current_slot["time_label"]
        remaining_minutes = current_slot["end"] - current_minutes
        remaining_seconds = remaining_minutes * 60 - current_seconds

        if phase == "work":
            next_time = next_slot["time_label"].split("–")[0].strip() if next_slot else "10:00 AM"
            status_message = "🚀 Agent Active: Searching fresh Naukri jobs..."
            next_event_label = f"Rest Break at {next_time} (in {remaining_minutes}m)"
        else:
            next_time = next_slot["time_label"].split("–")[0].strip() if next_slot else "09:00 AM"
            status_message = f"💤 Agent Resting (Next scan at {next_time} • in {remaining_minutes}m)"
            next_event_label = f"Next search at {next_time} (in {remaining_minutes}m)"

    return {
        "current_portal": "naukri",
        "portal_label": "Naukri.com",
        "phase": phase,  # "work" | "break" | "closed"
        "is_work_phase": (phase == "work"),
        "is_office_hours": is_office_hours,
        "slot_id": active_slot_id,
        "slot_label": slot_label,
        "status_message": status_message,
        "next_event_label": next_event_label,
        "remaining_minutes": remaining_minutes,
        "remaining_seconds": max(0, remaining_seconds),
        "active_window": "9:00 AM – 9:00 PM IST",
        "timetable_pattern": "1 Hour Work + 30 Min Break",
    }


class AutoPilotScheduler:
    def __init__(self):
        self._is_running = False
        self._task: Optional[asyncio.Task] = None
        self._last_run_date: Optional[str] = None
        self._last_run_time: Optional[str] = None
        self._last_run_report: Optional[Dict[str, Any]] = None
        self._daily_applications_count: int = 0
        self._daily_count_date: Optional[str] = None
        self._is_executing = False
        self._execution_lock: Optional[asyncio.Lock] = None
        self._last_execution_timestamp: float = 0.0
        self._last_scheduled_hour: Optional[int] = None
        self._last_executed_slot_id: Optional[int] = None
        self._last_enabled_state: Optional[bool] = None
        self._was_active_in_office_hours: bool = False
        self._wake_event: Optional[asyncio.Event] = None

    def nudge(self):
        """Immediately wakes up the scheduler loop to evaluate profile or setting changes."""
        if self._wake_event is not None:
            try:
                loop = asyncio.get_running_loop()
                loop.call_soon_threadsafe(self._wake_event.set)
            except RuntimeError:
                self._wake_event.set()

    def get_status(self) -> Dict[str, Any]:
        try:
            profile = load_profile()
            prefs = profile.preferences
        except Exception:
            prefs = None

        from app.db.session import SessionLocal
        from app.db import crud
        try:
            with SessionLocal() as db:
                self._daily_applications_count = crud.get_applied_today_count(db)
        except Exception:
            pass

        now = datetime.now()
        enabled = getattr(prefs, 'autopilot_enabled', False) if prefs else False
        auto_score = getattr(prefs, 'autopilot_auto_apply_score', 70) if prefs else 70
        max_apps = getattr(prefs, 'autopilot_max_daily_apps', 7) if prefs else 7

        is_office_hours = (OFFICE_START_HOUR <= now.hour < OFFICE_END_HOUR)

        if not enabled:
            next_run_str = "Disabled (Manual Only)"
        elif not is_office_hours:
            next_run_str = "Standby (Active Window: 9:00 AM – 9:00 PM)"
        else:
            next_run_str = "Active Office Hours (9:00 AM – 9:00 PM)"

        timeline_info = get_portal_timeline_slot(now)

        return {
            "enabled": enabled,
            "scheduled_time": "09:00 - 21:00",
            "auto_apply_score_threshold": auto_score,
            "max_daily_applications": max_apps,
            "daily_applications_count": self._daily_applications_count,
            "is_executing_now": self._is_executing,
            "last_run_date": self._last_run_date,
            "last_run_time": self._last_run_time,
            "last_run_report": self._last_run_report,
            "next_run": next_run_str,
            "timeline": timeline_info,
        }

    async def execute_run(self, trigger_source: str = "scheduler") -> Dict[str, Any]:
        """Runs the autonomous discovery and application cycle."""
        if self._execution_lock is None:
            self._execution_lock = asyncio.Lock()
        if self._execution_lock.locked() or self._is_executing:
            return {"status": "already_running", "message": "Auto-Pilot run is already in progress."}

        async with self._execution_lock:
            self._is_executing = True
            self._last_execution_timestamp = time.time()
            start_time = datetime.now()
        timeline_slot = get_portal_timeline_slot(start_time)
        active_portal = timeline_slot["current_portal"]
        portal_label = timeline_slot["portal_label"]
        slot_label = timeline_slot["slot_label"]

        # The daily cap must reset at the start of a new day, not only when status is polled
        today_str = start_time.strftime("%Y-%m-%d")
        if self._last_run_date != today_str and self._daily_count_date != today_str:
            self._daily_applications_count = 0
        self._daily_count_date = today_str
        logger.info(f"🚀 Auto-Pilot execution triggered ({trigger_source}) for {portal_label} ({slot_label}) at {start_time.isoformat()}...")

        emit_event("autopilot", "status", {
            "state": "running",
            "portal": active_portal,
            "portal_label": portal_label,
            "slot_label": slot_label,
            "message": f"Auto-Pilot started discovery scan on {portal_label} ({slot_label}) [{trigger_source}]."
        })

        try:
            profile = load_profile()
            prefs = profile.preferences
            target_roles = getattr(prefs, 'target_roles', []) or ["Junior AI Engineer", "Python Developer"]
            locations = getattr(prefs, 'preferred_locations', []) or ["Hyderabad", "Bengaluru"]
            freshness = getattr(prefs, 'freshness_days', 1)
            auto_score = getattr(prefs, 'autopilot_auto_apply_score', 70)
            max_daily = getattr(prefs, 'autopilot_max_daily_apps', 7) or 7

            from app.db.session import SessionLocal
            from app.db import crud
            from app.agent.applier import EasyApplyFiller

            applied_in_this_run = 0
            filler = EasyApplyFiller(headless=True)
            report = None

            async def _attempt_auto_apply(job, db, filler_engine, min_score) -> bool:
                score = job.evaluation.match_score if job.evaluation else 0
                if score < min_score or not job.job_url:
                    return False
                logger.info(f"⚡ Auto-applying to '{job.job_title}' at '{job.company_name}' (Score: {score}% >= {min_score}%)...")
                try:
                    pdf_path = job.applications[0].tailored_resume_pdf_path if job.applications else None
                    res = await asyncio.to_thread(
                        filler_engine.fill_and_stage_application,
                        target_url_or_path=job.job_url,
                        resume_path=pdf_path,
                        job_title=job.job_title,
                        company_name=job.company_name,
                        thread_id=f"autopilot_{job.id}_{int(datetime.now().timestamp())}",
                        auto_submit=True
                    )
                    portal_tag = "Indeed" if "indeed.com" in (job.job_url or "").lower() else "Naukri"
                    if res.status == "SUBMITTED":
                        crud.create_or_update_application(
                            db=db,
                            job_id=job.id,
                            status="Applied",
                            notes=f"Auto-applied by Smart Auto-Pilot via {portal_tag} 1-Click Apply (Score: {score}%)."
                        )
                        return True
                    elif res.status == "ALREADY_APPLIED":
                        crud.create_or_update_application(
                            db=db,
                            job_id=job.id,
                            status="Applied",
                            notes=f"Already applied on {portal_tag}. Detected by Auto-Pilot."
                        )
                        return False
                    elif res.status == "EXTERNAL_SITE":
                        crud.create_or_update_application(
                            db=db,
                            job_id=job.id,
                            status="Ready",
                            notes=f"External Company Portal on {portal_tag}: Requires direct manual application."
                        )
                        return False
                    elif res.status == "LOGIN_REQUIRED":
                        logger.warning(f"{portal_tag} login session is not authenticated. Halting auto-apply.")
                        return False
                except Exception as apply_err:
                    logger.warning(f"Auto-apply error on Job {job.id}: {apply_err}")
                return False

            with SessionLocal() as db:
                # 1. Sync daily application count with actual database records for the last 24h
                self._daily_applications_count = crud.get_applied_today_count(db)
                logger.info(f"📊 Auto-Pilot quota check: {self._daily_applications_count}/{max_daily} applications submitted in past 24 hours.")

                # 2. Step 1: Drain leftover unapplied jobs from Review ('Ready') up to daily limit
                if AUTOPILOT_AUTO_SUBMIT and self._daily_applications_count < max_daily:
                    existing_ready = crud.list_jobs(db=db, limit=50, status="Ready")
                    candidates = [
                        j for j in existing_ready 
                        if (j.evaluation and j.evaluation.match_score >= auto_score)
                        and "External Company Portal" not in (j.applications[0].notes if j.applications else "")
                    ]
                    if candidates:
                        logger.info(f"🔄 Found {len(candidates)} leftover jobs in Review. Applying up to daily quota ({max_daily})...")
                        for job in candidates:
                            if self._daily_applications_count >= max_daily:
                                logger.info(f"Daily safety quota reached ({self._daily_applications_count}/{max_daily}). Leftover jobs stay in Review for tomorrow.")
                                break
                            applied = await _attempt_auto_apply(job, db, filler, auto_score)
                            if applied:
                                self._daily_applications_count += 1
                                applied_in_this_run += 1
                elif self._daily_applications_count >= max_daily:
                    logger.info(f"Daily safety quota already reached ({self._daily_applications_count}/{max_daily}). Auto-apply paused for today; jobs remain queued for tomorrow.")

                # 3. Step 2: Discover fresh jobs for the scheduled portal (new jobs queue in Review when quota full)
                search_term = target_roles[0] if target_roles else "AI Engineer"
                search_loc = locations[0] if locations else "Hyderabad"

                exp_level = getattr(prefs, 'experience_level', '0-1')
                report = await discover_and_ingest(
                    search_term=search_term,
                    search_terms=target_roles[:3] if target_roles else None,
                    location=search_loc,
                    locations=locations[:2] if locations else None,
                    portals=[active_portal],
                    results_wanted=15,
                    freshness_days=freshness,
                    experience_level=exp_level,
                    min_match_score=READY_MATCH_THRESHOLD,
                    max_jobs_to_process=12,
                )

                # 4. Sync application counts after discovery run
                new_daily_count = crud.get_applied_today_count(db)
                applied_in_this_run += max(0, new_daily_count - self._daily_applications_count)
                self._daily_applications_count = new_daily_count

                # Final count of jobs currently waiting in Review
                review_remaining = len(crud.list_jobs(db=db, limit=100, status="Ready"))

            self._last_run_date = datetime.now().strftime("%Y-%m-%d")
            self._last_run_time = datetime.now().strftime("%H:%M:%S")
            self._last_run_report = {
                "discovered": report.total_discovered if report else 0,
                "ready_for_review": review_remaining,
                "auto_applied": applied_in_this_run,
                "daily_total_applied": self._daily_applications_count,
                "max_daily_quota": max_daily,
                "archived": report.low_matches_archived if report else 0,
                "completed_at": self._last_run_time,
                "portal_searched": active_portal,
                "portal_label": portal_label,
                "slot_label": slot_label,
            }

            emit_event("autopilot", "status", {
                "state": "idle",
                "portal": active_portal,
                "portal_label": portal_label,
                "slot_label": slot_label,
                "message": f"Auto-Pilot completed for {portal_label} ({slot_label})! {applied_in_this_run} auto-applied today ({self._daily_applications_count}/{max_daily}). {review_remaining} waiting in Review queue."
            })

            return {
                "status": "success",
                "report": self._last_run_report
            }

        except Exception as e:
            logger.error(f"Auto-Pilot Run Error: {e}", exc_info=True)
            emit_event("autopilot", "status", {
                "state": "error",
                "message": f"Auto-Pilot run notice: {str(e)}"
            })
            return {"status": "error", "detail": str(e)}
        finally:
            self._is_executing = False

    async def _loop(self):
        """Background loop managing dynamic office hours (9:00 AM – 9:00 PM)."""
        logger.info("🕒 Auto-Pilot Scheduler background loop active (Office Hours: 9:00 AM – 9:00 PM).")
        while self._is_running:
            try:
                profile = load_profile()
                prefs = profile.preferences
                enabled = getattr(prefs, 'autopilot_enabled', False)
                now = datetime.now()

                timeline_info = get_portal_timeline_slot(now)
                is_office_hours = timeline_info["is_office_hours"]
                phase = timeline_info["phase"]
                slot_id = timeline_info["slot_id"]

                # 1. Automatic 9:00 PM Cutoff: Turn OFF when 9:00 PM is reached
                if enabled and (now.hour >= OFFICE_END_HOUR or now.hour < OFFICE_START_HOUR):
                    if self._was_active_in_office_hours or now.hour >= OFFICE_END_HOUR:
                        logger.info("🌙 9:00 PM reached. Office hours closed. Auto-Pilot automatically turning OFF.")
                        prefs.autopilot_enabled = False
                        profile_file = BASE_DIR / "profile.json"
                        with open(profile_file, "w", encoding="utf-8") as f:
                            json.dump(profile.model_dump(), f, indent=2)
                        self._was_active_in_office_hours = False
                        self._last_enabled_state = False
                        self._last_executed_slot_id = None
                        emit_event("autopilot", "status", {
                            "state": "idle",
                            "enabled": False,
                            "phase": "closed",
                            "message": "🌙 9:00 PM reached. Office hours ended. Auto-Pilot automatically turned OFF."
                        })
                        if self._wake_event is not None:
                            try:
                                await asyncio.wait_for(self._wake_event.wait(), timeout=15.0)
                                self._wake_event.clear()
                            except asyncio.TimeoutError:
                                pass
                        else:
                            await asyncio.sleep(15)
                        continue

                # 2. Inside Office Hours (9:00 AM – 9:00 PM): 1-Hour Work + 30-Min Rest Cadence
                if is_office_hours:
                    self._was_active_in_office_hours = True
                    if enabled and not self._is_executing:
                        if phase == "work" and self._last_executed_slot_id != slot_id:
                            self._last_executed_slot_id = slot_id
                            logger.info(f"⏰ Work Slot {slot_id} reached ({timeline_info['slot_label']}). Starting autonomous Naukri scan...")
                            asyncio.create_task(self.execute_run(trigger_source=f"work_slot_{slot_id}"))
                else:
                    self._was_active_in_office_hours = False
                    self._last_scheduled_hour = None
                    self._last_executed_slot_id = None

            except Exception as loop_err:
                logger.warning(f"Auto-Pilot ticker notice: {loop_err}")

            if self._wake_event is not None:
                try:
                    await asyncio.wait_for(self._wake_event.wait(), timeout=15.0)
                    self._wake_event.clear()
                except asyncio.TimeoutError:
                    pass
            else:
                await asyncio.sleep(15)

    def start(self):
        if not self._is_running:
            self._is_running = True
            self._wake_event = asyncio.Event()
            self._task = asyncio.create_task(self._loop())

    def stop(self):
        self._is_running = False
        if self._task and not self._task.done():
            self._task.cancel()


autopilot_scheduler = AutoPilotScheduler()
