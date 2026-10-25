"""
Module: scheduler.py
Purpose: Smart Auto-Pilot Background Scheduler for Autonomous Job Agent.
Standards: Rule 1 (Zero Blind Trust), Rule 2 (Type & Schema Safety), Rule 5 (Production Reliability).
"""
import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from app.agent.scorer import load_profile
from app.agent.ingestion import discover_and_ingest
from app.utils.event_bus import emit_event

logger = logging.getLogger("agent.scheduler")


class AutoPilotScheduler:
    def __init__(self):
        self._is_running = False
        self._task: Optional[asyncio.Task] = None
        self._last_run_date: Optional[str] = None
        self._last_run_time: Optional[str] = None
        self._last_run_report: Optional[Dict[str, Any]] = None
        self._daily_applications_count: int = 0
        self._is_executing = False

    def get_status(self) -> Dict[str, Any]:
        try:
            profile = load_profile()
            prefs = profile.preferences
        except Exception:
            prefs = None

        today_str = datetime.now().strftime("%Y-%m-%d")
        if self._last_run_date != today_str:
            self._daily_applications_count = 0

        target_hour = getattr(prefs, 'autopilot_run_hour', 22) if prefs else 22
        target_minute = getattr(prefs, 'autopilot_run_minute', 30) if prefs else 30
        enabled = getattr(prefs, 'autopilot_enabled', False) if prefs else False
        auto_score = getattr(prefs, 'autopilot_auto_apply_score', 80) if prefs else 80
        max_apps = getattr(prefs, 'autopilot_max_daily_apps', 12) if prefs else 12

        next_run_str = f"Tonight at {target_hour:02d}:{target_minute:02d}" if enabled else "Disabled"

        return {
            "enabled": enabled,
            "scheduled_time": f"{target_hour:02d}:{target_minute:02d}",
            "auto_apply_score_threshold": auto_score,
            "max_daily_applications": max_apps,
            "daily_applications_count": self._daily_applications_count,
            "is_executing_now": self._is_executing,
            "last_run_date": self._last_run_date,
            "last_run_time": self._last_run_time,
            "last_run_report": self._last_run_report,
            "next_run": next_run_str,
        }

    async def execute_run(self, trigger_source: str = "scheduler") -> Dict[str, Any]:
        """Runs the autonomous discovery and application cycle."""
        if self._is_executing:
            return {"status": "already_running", "message": "Auto-Pilot run is already in progress."}

        self._is_executing = True
        start_time = datetime.now()
        logger.info(f"🚀 Auto-Pilot execution triggered ({trigger_source}) at {start_time.isoformat()}...")

        emit_event("autopilot", "status", {
            "state": "running",
            "message": f"Auto-Pilot started discovery scan ({trigger_source})."
        })

        try:
            profile = load_profile()
            prefs = profile.preferences
            target_roles = getattr(prefs, 'target_roles', []) or ["Junior AI Engineer", "Python Developer"]
            locations = getattr(prefs, 'preferred_locations', []) or ["Hyderabad", "Remote"]
            freshness = getattr(prefs, 'freshness_days', 1)
            auto_score = getattr(prefs, 'autopilot_auto_apply_score', 80)
            max_daily = getattr(prefs, 'autopilot_max_daily_apps', 12)

            search_term = target_roles[0] if target_roles else "AI Engineer"
            search_loc = locations[0] if locations else "Hyderabad"

            # Ingest jobs with 3-tier routing:
            # Low (<70%) -> Archived, Medium (70-79%) -> Ready, High (>=80%) -> Ready for Auto-Apply
            report = await discover_and_ingest(
                search_term=search_term,
                location=search_loc,
                portals=["naukri"],
                results_wanted=15,
                freshness_days=freshness,
                min_match_score=70,  # Ready queue threshold
                max_jobs_to_process=12,
            )

            # Auto-apply to jobs that meet score >= auto_score
            applied_in_this_run = 0
            from app.db.session import SessionLocal
            from app.db import crud
            from app.agent.applier import EasyApplyFiller

            with SessionLocal() as db:
                ready_jobs = crud.list_jobs(db=db, limit=20, status="Ready")
                filler = EasyApplyFiller(headless=True)

                for job in ready_jobs:
                    if self._daily_applications_count >= max_daily:
                        logger.info(f"Daily safety quota reached ({self._daily_applications_count}/{max_daily}). Stopping auto-applications.")
                        break

                    score = job.evaluation.match_score if job.evaluation else 0
                    if score >= auto_score and job.job_url:
                        logger.info(f"⚡ Auto-applying to '{job.job_title}' at '{job.company_name}' (Score: {score}% >= {auto_score}%)...")
                        try:
                            res = await asyncio.to_thread(
                                filler.fill_and_stage_application,
                                target_url_or_path=job.job_url,
                                resume_path=job.applications[0].tailored_resume_pdf_path if job.applications else None,
                                job_title=job.job_title,
                                company_name=job.company_name,
                                thread_id=f"autopilot_{job.id}_{int(datetime.now().timestamp())}",
                                auto_submit=True
                            )
                            if res.status == "SUBMITTED":
                                crud.create_or_update_application(
                                    db=db,
                                    job_id=job.id,
                                    status="Applied",
                                    notes=f"Auto-applied by Smart Auto-Pilot (Score: {score}%). Screenshot: {res.confirmation_snapshot_path or ''}"
                                )
                                self._daily_applications_count += 1
                                applied_in_this_run += 1
                        except Exception as apply_err:
                            logger.warning(f"Auto-apply error on Job {job.id}: {apply_err}")

            self._last_run_date = datetime.now().strftime("%Y-%m-%d")
            self._last_run_time = datetime.now().strftime("%H:%M:%S")
            ready_remaining = max(0, report.high_matches_ready - applied_in_this_run)
            self._last_run_report = {
                "discovered": report.total_discovered,
                "ready_for_review": ready_remaining,
                "auto_applied": applied_in_this_run,
                "archived": report.low_matches_archived,
                "completed_at": self._last_run_time
            }

            emit_event("autopilot", "status", {
                "state": "idle",
                "message": f"Auto-Pilot completed! {applied_in_this_run} auto-applied, {ready_remaining} ready for review."
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
        """Background ticker checking every 30 seconds."""
        logger.info("🕒 Auto-Pilot Scheduler background loop active.")
        while self._is_running:
            try:
                profile = load_profile()
                prefs = profile.preferences
                enabled = getattr(prefs, 'autopilot_enabled', False)

                if enabled and not self._is_executing:
                    now = datetime.now()
                    target_hour = getattr(prefs, 'autopilot_run_hour', 22)
                    target_minute = getattr(prefs, 'autopilot_run_minute', 30)

                    today_str = now.strftime("%Y-%m-%d")
                    # Check if current time matches scheduled minute and hasn't run yet today
                    if now.hour == target_hour and now.minute == target_minute and self._last_run_date != today_str:
                        logger.info(f"⏰ Scheduled Auto-Pilot time reached ({target_hour:02d}:{target_minute:02d}). Starting run...")
                        await self.execute_run(trigger_source="night_schedule")

            except Exception as loop_err:
                logger.warning(f"Auto-Pilot ticker notice: {loop_err}")

            await asyncio.sleep(30)

    def start(self):
        if not self._is_running:
            self._is_running = True
            self._task = asyncio.create_task(self._loop())

    def stop(self):
        self._is_running = False
        if self._task and not self._task.done():
            self._task.cancel()


autopilot_scheduler = AutoPilotScheduler()
