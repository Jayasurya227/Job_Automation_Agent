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
PERIODIC_INTERVAL_SECONDS = 3600  # 1 hour between periodic daytime crawls


def get_portal_timeline_slot(dt: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Resolves the single active portal for the 12-Hour Round-Robin hourly rotation.
    Active Window: 9:00 AM – 9:00 PM (09:00 to 21:00 IST).
    Rotates strictly between Naukri and Indeed by hour:
       9:00 AM – 10:00 AM: Naukri
      10:00 AM – 11:00 AM: Indeed
      11:00 AM – 12:00 PM: Naukri
      12:00 PM –  1:00 PM: Indeed
       1:00 PM –  2:00 PM: Naukri
       2:00 PM –  3:00 PM: Indeed
       3:00 PM –  4:00 PM: Naukri
       4:00 PM –  5:00 PM: Indeed
       5:00 PM –  6:00 PM: Naukri
       6:00 PM –  7:00 PM: Indeed
       7:00 PM –  8:00 PM: Naukri
       8:00 PM –  9:00 PM: Indeed
    """
    now = dt or datetime.now()
    hour = now.hour
    is_office_hours = (OFFICE_START_HOUR <= hour < OFFICE_END_HOUR)

    # 12-hour rotation starting at OFFICE_START_HOUR: Even offsets -> Naukri, Odd offsets -> Indeed
    if (hour - OFFICE_START_HOUR) % 2 == 0:
        current_portal = "naukri"
        next_portal = "indeed"
    else:
        current_portal = "indeed"
        next_portal = "naukri"

    def format_hour(h: int) -> str:
        period = "AM" if h < 12 else "PM"
        disp = h if (0 < h <= 12) else (h - 12 if h > 12 else 12)
        return f"{disp}:00 {period}"

    slot_start = format_hour(hour)
    slot_end = format_hour((hour + 1) % 24)
    next_slot_end = format_hour((hour + 2) % 24)

    return {
        "current_portal": current_portal,
        "portal_label": "Naukri.com" if current_portal == "naukri" else "Indeed",
        "slot_label": f"{slot_start} – {slot_end}",
        "next_portal": next_portal,
        "next_portal_label": "Naukri.com" if next_portal == "naukri" else "Indeed",
        "next_slot_label": f"{slot_end} – {next_slot_end}",
        "is_office_hours": is_office_hours,
        "active_window": "9:00 AM – 9:00 PM IST",
        "hour": hour
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

                # Office hours window: 9:00 AM to 9:00 PM (21:00)
                is_office_hours = (OFFICE_START_HOUR <= now.hour < OFFICE_END_HOUR)

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
                        emit_event("autopilot", "status", {
                            "state": "idle",
                            "enabled": False,
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

                # 2. Inside Office Hours (9:00 AM – 9:00 PM)
                if is_office_hours:
                    self._was_active_in_office_hours = True
                    if enabled and not self._is_executing:
                        if self._last_scheduled_hour != now.hour:
                            self._last_scheduled_hour = now.hour
                            logger.info(f"⏰ Hourly Auto-Pilot slot reached ({now.hour}:00 IST). Starting execution for scheduled portal...")
                            asyncio.create_task(self.execute_run(trigger_source=f"hourly_slot_{now.hour}"))
                else:
                    self._was_active_in_office_hours = False
                    self._last_scheduled_hour = None

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
