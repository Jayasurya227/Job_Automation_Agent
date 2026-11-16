"""
Module: scheduler.py
Purpose: Dynamic Multi-Tenant Office Hours Auto-Pilot Background Scheduler for Autonomous Job Agent.
         Active Window: 9:00 AM – 9:00 PM IST (09:00 – 21:00).
         - Triggers immediate discovery & 1-click apply as soon as Auto-Pilot is turned ON during office hours.
         - Automatically shuts OFF at 9:00 PM sharp per user profile in isolated storage vaults.
         - Periodically searches and applies during office hours using 1-Hour Work + 30-Minute Rest cadence.
         - Strictly scoped to user_id: Each user has their own independent daily quota, timetable, and state.
Standards: Rule 1 (Zero Blind Trust), Rule 2 (Type & Schema Safety), Rule 3 (Low Code & High Signal), Rule 5 (Production Reliability).
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List

from app.config import READY_MATCH_THRESHOLD, AUTOPILOT_AUTO_SUBMIT, BASE_DIR
from app.core.user_storage import load_user_profile, save_user_profile
from app.db.session import SessionLocal
from app.db.models import User
from app.db import crud
from app.agent.task_queue import task_queue
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


def get_portal_timeline_slot(dt: Optional[datetime] = None, user_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Resolves the exact 1-Hour Work + 30-Minute Break timetable slot for Naukri.
    Active Office Window: 9:00 AM – 9:00 PM IST (09:00 to 21:00).
    Scoped dynamically per user_id to showcase candidate's rotating priority roles.
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

    # Dynamically resolve active and next rotating role for current slot (Round-Robin Allocation)
    active_role = None
    next_role = None
    try:
        profile = load_user_profile(user_id or 1)
        target_roles = getattr(profile.preferences, "target_roles", []) or []
        if target_roles:
            if active_slot_id > 0:
                active_role = target_roles[(active_slot_id - 1) % len(target_roles)]
                next_role = target_roles[active_slot_id % len(target_roles)]
            else:
                next_role = target_roles[0]
                active_role = None

            if phase == "work":
                status_message = f"🚀 Agent Active: Scanning Naukri for '{active_role}'..."
            elif phase == "break":
                status_message = f"💤 Agent Resting (Next: '{next_role}' at {next_time} • in {remaining_minutes}m)"
            elif phase == "closed":
                status_message = f"🌙 Office Hours Closed (Resumes 9:00 AM with '{next_role}')"
    except Exception:
        active_role = None
        next_role = None

    return {
        "current_portal": "naukri",
        "portal_label": "Naukri.com",
        "phase": phase,  # "work" | "break" | "closed"
        "is_work_phase": (phase == "work"),
        "is_office_hours": is_office_hours,
        "slot_id": active_slot_id,
        "slot_label": slot_label,
        "active_role": active_role,
        "next_role": next_role,
        "status_message": status_message,
        "next_event_label": next_event_label,
        "remaining_minutes": remaining_minutes,
        "remaining_seconds": max(0, remaining_seconds),
        "active_window": "9:00 AM – 9:00 PM IST",
        "timetable_pattern": "1 Hour Work + 30 Min Break",
    }


class AutoPilotScheduler:
    """
    Enterprise Multi-Tenant AutoPilot Engine.
    Handles independent time windows, daily quotas, profile boosting,
    and automatic 9:00 PM shutoff per user without cross-tenant collisions.
    """
    def __init__(self):
        self._is_running = False
        self._task: Optional[asyncio.Task] = None
        self._wake_event: Optional[asyncio.Event] = None
        self._last_executed_slot_id: Optional[int] = None
        self._user_states: Dict[int, Dict[str, Any]] = {}
        self._user_locks: Dict[int, asyncio.Lock] = {}

    def _get_user_lock(self, user_id: int) -> asyncio.Lock:
        if user_id not in self._user_locks:
            self._user_locks[user_id] = asyncio.Lock()
        return self._user_locks[user_id]

    def _get_or_create_user_state(self, user_id: int) -> Dict[str, Any]:
        if user_id not in self._user_states:
            self._user_states[user_id] = {
                "daily_applications_count": 0,
                "daily_count_date": None,
                "last_run_date": None,
                "last_run_time": None,
                "last_run_report": None,
                "last_boost_date": None,
                "is_executing": False,
            }
        return self._user_states[user_id]

    def nudge(self):
        """Immediately wakes up the scheduler loop to evaluate profile or setting changes."""
        if self._wake_event is not None:
            try:
                loop = asyncio.get_running_loop()
                loop.call_soon_threadsafe(self._wake_event.set)
            except RuntimeError:
                self._wake_event.set()

    def get_status(self, user_id: int = 1) -> Dict[str, Any]:
        """Returns the real-time status of the Auto-Pilot scheduler scoped strictly to user_id."""
        state = self._get_or_create_user_state(user_id)
        try:
            profile = load_user_profile(user_id)
            prefs = profile.preferences
        except Exception:
            prefs = None

        try:
            with SessionLocal() as db:
                state["daily_applications_count"] = crud.get_applied_today_count(db, user_id=user_id)
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

        timeline_info = get_portal_timeline_slot(now, user_id=user_id)

        return {
            "user_id": user_id,
            "enabled": enabled,
            "scheduled_time": "09:00 - 21:00",
            "auto_apply_score_threshold": auto_score,
            "max_daily_applications": max_apps,
            "daily_applications_count": state["daily_applications_count"],
            "is_executing_now": state["is_executing"],
            "last_run_date": state["last_run_date"],
            "last_run_time": state["last_run_time"],
            "last_run_report": state["last_run_report"],
            "next_run": next_run_str,
            "timeline": timeline_info,
        }

    async def execute_run(self, user_id: int = 1, trigger_source: str = "scheduler") -> Dict[str, Any]:
        """
        Executes an autonomous discovery & 1-click application run strictly scoped to user_id.
        User 1 and User 2 have independent locks, so both can run concurrently without blocking.
        """
        user_lock = self._get_user_lock(user_id)
        state = self._get_or_create_user_state(user_id)

        if user_lock.locked() or state["is_executing"]:
            return {
                "status": "already_running",
                "user_id": user_id,
                "message": f"Auto-Pilot run is already in progress for User {user_id}."
            }

        async with user_lock:
            state["is_executing"] = True
            start_time = datetime.now()

            timeline_slot = get_portal_timeline_slot(start_time, user_id=user_id)
            active_portal = "naukri"
            portal_label = "Naukri.com"
            slot_label = timeline_slot["slot_label"]

            today_str = start_time.strftime("%Y-%m-%d")
            if state["last_run_date"] != today_str and state["daily_count_date"] != today_str:
                state["daily_applications_count"] = 0
            state["daily_count_date"] = today_str

            logger.info(f"🚀 [User {user_id}] Auto-Pilot triggered ({trigger_source}) for {portal_label} ({slot_label}) at {start_time.isoformat()}...")

            status_payload = {
                "user_id": user_id,
                "state": "running",
                "portal": active_portal,
                "portal_label": portal_label,
                "slot_label": slot_label,
                "message": f"Auto-Pilot started discovery scan on {portal_label} ({slot_label}) [{trigger_source}]."
            }
            emit_event(f"autopilot:{user_id}", "status", status_payload)
            emit_event("autopilot", "status", status_payload)

            try:
                profile = load_user_profile(user_id)
                prefs = profile.preferences
                target_roles = getattr(prefs, 'target_roles', []) or ["Junior AI Engineer", "Python Developer"]
                locations = getattr(prefs, 'preferred_locations', []) or ["Hyderabad", "Bengaluru"]
                freshness = getattr(prefs, 'freshness_days', 1)
                auto_score = getattr(prefs, 'autopilot_auto_apply_score', 70)
                max_daily = getattr(prefs, 'autopilot_max_daily_apps', 7) or 7

                from app.agent.booster import boost_naukri_profile_live
                from app.agent.ingestion import process_1click_applications, discover_and_ingest

                applied_in_this_run = 0

                with SessionLocal() as db:
                    # 1. Sync daily application count strictly for this user
                    state["daily_applications_count"] = crud.get_applied_today_count(db, user_id=user_id)
                    logger.info(f"📊 [User {user_id}] Auto-Pilot quota check: {state['daily_applications_count']}/{max_daily} applications submitted today.")

                    # 2. Trigger daily Recruiter Profile Booster (Resdex Freshness) strictly for this user
                    if state.get("last_boost_date") != today_str:
                        logger.info(f"🚀 [User {user_id}] Triggering daily Recruiter Profile Booster (Resdex Freshness)...")
                        try:
                            await boost_naukri_profile_live(user_id=user_id)
                            state["last_boost_date"] = today_str
                        except Exception as boost_err:
                            logger.warning(f"Profile booster notice for User {user_id}: {boost_err}")

                    # 3. Step 1: Drain leftover unapplied jobs from Review ('Ready') up to daily limit
                    if AUTOPILOT_AUTO_SUBMIT and state["daily_applications_count"] < max_daily:
                        apply_res = await process_1click_applications(
                            user_id=user_id,
                            max_daily_limit=max_daily,
                            min_score=auto_score,
                        )
                        applied_in_this_run += apply_res.get("applied_count", 0)
                        state["daily_applications_count"] = apply_res.get("daily_total", state["daily_applications_count"])
                    elif state["daily_applications_count"] >= max_daily:
                        logger.info(f"Daily safety quota reached for User {user_id} ({state['daily_applications_count']}/{max_daily}). Auto-apply paused for today.")
                        emit_event(f"autopilot:{user_id}", "quota_reached", {"user_id": user_id, "applied_today": state["daily_applications_count"], "max_daily": max_daily})
                        emit_event("autopilot", "quota_reached", {"user_id": user_id, "applied_today": state["daily_applications_count"], "max_daily": max_daily})

                    # 4. Step 2: Discover fresh listings for Naukri (Dynamic Slot Rotation)
                    slot_id = timeline_slot.get("slot_id") or 1
                    if target_roles and slot_id > 0:
                        slot_idx = (slot_id - 1) % len(target_roles)
                        rotated_roles = [target_roles[slot_idx]] + [r for i, r in enumerate(target_roles) if i != slot_idx]
                    else:
                        rotated_roles = target_roles

                    search_term = rotated_roles[0] if rotated_roles else "AI Engineer"
                    search_loc = locations[0] if locations else "Hyderabad"

                    logger.info(f"🔄 [User {user_id}] Slot #{slot_id} Domain Rotation: Priority role '{search_term}'...")

                    exp_level = getattr(prefs, 'experience_level', '0-1')
                    report = await discover_and_ingest(
                        search_term=search_term,
                        search_terms=rotated_roles[:3] if rotated_roles else None,
                        location=search_loc,
                        locations=locations[:2] if locations else None,
                        portals=["naukri"],
                        results_wanted=20,
                        freshness_days=freshness,
                        experience_level=exp_level,
                        min_match_score=READY_MATCH_THRESHOLD,
                        max_jobs_to_process=None,
                        user_id=user_id,
                    )

                    # 5. Sync application counts after discovery run
                    new_daily_count = crud.get_applied_today_count(db, user_id=user_id)
                    applied_in_this_run += max(0, new_daily_count - state["daily_applications_count"])
                    state["daily_applications_count"] = new_daily_count

                    review_remaining = len(crud.list_jobs(db=db, limit=100, status="Ready", user_id=user_id))

                state["last_run_date"] = datetime.now().strftime("%Y-%m-%d")
                state["last_run_time"] = datetime.now().strftime("%H:%M:%S")
                state["last_run_report"] = {
                    "user_id": user_id,
                    "discovered": report.total_discovered if report else 0,
                    "ready_for_review": review_remaining,
                    "auto_applied": applied_in_this_run,
                    "daily_total_applied": state["daily_applications_count"],
                    "max_daily_quota": max_daily,
                    "archived": report.low_matches_archived if report else 0,
                    "completed_at": state["last_run_time"],
                    "portal_searched": active_portal,
                    "portal_label": portal_label,
                    "slot_label": slot_label,
                }

                completed_payload = {
                    "user_id": user_id,
                    "state": "idle",
                    "portal": active_portal,
                    "portal_label": portal_label,
                    "slot_label": slot_label,
                    "message": f"Auto-Pilot completed for User {user_id}! {applied_in_this_run} auto-applied today ({state['daily_applications_count']}/{max_daily}). {review_remaining} waiting in Review queue."
                }
                emit_event(f"autopilot:{user_id}", "status", completed_payload)
                emit_event("autopilot", "status", completed_payload)

                return {
                    "status": "success",
                    "user_id": user_id,
                    "report": state["last_run_report"]
                }

            except Exception as e:
                logger.error(f"Auto-Pilot Run Error for User {user_id}: {e}", exc_info=True)
                err_payload = {
                    "user_id": user_id,
                    "state": "error",
                    "message": f"Auto-Pilot notice for User {user_id}: {str(e)}"
                }
                emit_event(f"autopilot:{user_id}", "status", err_payload)
                emit_event("autopilot", "status", err_payload)
                return {"status": "error", "user_id": user_id, "detail": str(e)}
            finally:
                state["is_executing"] = False

    async def execute_all_active_users(self, trigger_source: str = "scheduler_tick"):
        """
        Iterates dynamically over all active users in the database and triggers their
        Auto-Pilot execution if enabled. Zero hardcoded limits on user count.
        """
        active_user_ids = []
        try:
            with SessionLocal() as db:
                users = db.query(User).filter(User.is_active == True).all()
                active_user_ids = [u.id for u in users]
        except Exception as db_err:
            logger.warning(f"Failed to query active users for scheduler: {db_err}")
            active_user_ids = [1]

        logger.info(f"🔄 Evaluating Auto-Pilot for {len(active_user_ids)} active user(s): {active_user_ids}...")
        for uid in active_user_ids:
            try:
                prof = load_user_profile(uid)
                if getattr(prof.preferences, "autopilot_enabled", False):
                    # Enqueue or launch execution asynchronously
                    asyncio.create_task(self.execute_run(user_id=uid, trigger_source=trigger_source))
            except Exception as u_err:
                logger.debug(f"User {uid} profile evaluation notice: {u_err}")

    async def _loop(self):
        """Background loop managing dynamic office hours (9:00 AM – 9:00 PM IST)."""
        logger.info("🕒 Auto-Pilot Scheduler background loop active (Office Hours: 9:00 AM – 9:00 PM IST).")
        while self._is_running:
            try:
                now = datetime.now()
                timeline_info = get_portal_timeline_slot(now)
                is_office_hours = timeline_info["is_office_hours"]
                phase = timeline_info["phase"]
                slot_id = timeline_info["slot_id"]

                # 1. Automatic 9:00 PM Cutoff: Turn OFF for all users when 9:00 PM is reached
                if now.hour >= OFFICE_END_HOUR or now.hour < OFFICE_START_HOUR:
                    # Office hours are closed
                    try:
                        with SessionLocal() as db:
                            users = db.query(User).filter(User.is_active == True).all()
                            uids = [u.id for u in users]
                    except Exception:
                        uids = [1]

                    for uid in uids:
                        try:
                            prof = load_user_profile(uid)
                            if getattr(prof.preferences, "autopilot_enabled", False):
                                logger.info(f"🌙 [User {uid}] 9:00 PM reached. Office hours closed. Auto-Pilot automatically turning OFF.")
                                prof.preferences.autopilot_enabled = False
                                save_user_profile(uid, prof)
                                cutoff_payload = {
                                    "user_id": uid,
                                    "state": "idle",
                                    "enabled": False,
                                    "phase": "closed",
                                    "message": "🌙 9:00 PM reached. Office hours ended. Auto-Pilot automatically turned OFF."
                                }
                                emit_event(f"autopilot:{uid}", "status", cutoff_payload)
                                emit_event("autopilot", "status", cutoff_payload)
                        except Exception:
                            pass

                # 2. Inside Office Hours (9:00 AM – 9:00 PM): 1-Hour Work + 30-Min Rest Cadence
                elif is_office_hours:
                    if phase == "work" and self._last_executed_slot_id != slot_id:
                        self._last_executed_slot_id = slot_id
                        logger.info(f"⏰ Work Slot {slot_id} reached ({timeline_info['slot_label']}). Triggering Auto-Pilot for all enabled users...")
                        await self.execute_all_active_users(trigger_source=f"work_slot_{slot_id}")

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
        """Starts the scheduler loop and initializes the task queue."""
        if not self._is_running:
            self._is_running = True
            self._wake_event = asyncio.Event()
            task_queue.start()
            self._task = asyncio.create_task(self._loop())
            logger.info("🚀 AutoPilotScheduler started.")

    def stop(self):
        """Stops the scheduler loop gracefully."""
        self._is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("🛑 AutoPilotScheduler stopped.")


# Global singleton instance
autopilot_scheduler = AutoPilotScheduler()
