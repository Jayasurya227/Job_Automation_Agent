"""
Autonomous Ingestion & AI Scoring Pipeline.
Receives raw discovered jobs from multi-portal scraper, checks SQLite deduplication,
evaluates ATS match with Gemini, and auto-triages jobs into 'Ready' (>= READY_MATCH_THRESHOLD) or 'Archived' (below it).
For high-match jobs, automatically generates tailored LaTeX resumes and recruiter outreach packages.
Part of Phase 3: Browser Automation & Job Discovery.
"""

import logging
import asyncio
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field

from app.config import READY_MATCH_THRESHOLD, AUTO_APPLY_MATCH_THRESHOLD
from app.agent.scraper import DiscoveredJob, discover_jobs, load_candidate_preferences
from app.agent.scorer import analyze_and_score_job
from app.agent.outreach import generate_outreach
from app.db.session import SessionLocal
from app.db import crud
from app.db.crud import (
    create_job,
    save_job_evaluation,
    create_or_update_application,
    maintain_top_active_jobs,
    job_exists,
)
from app.utils.event_bus import emit_event

logger = logging.getLogger("agent.ingestion")

_discovery_lock = asyncio.Lock()

DEFAULT_PROFILE_PATH = Path(__file__).resolve().parent.parent.parent / "profile.json"


class IngestionJobResult(BaseModel):
    """Result summary for an individual ingested job listing."""
    job_id: int = Field(..., description="SQLite primary key ID")
    title: str = Field(..., description="Job title")
    company: str = Field(..., description="Company name")
    portal: str = Field(..., description="Portal discovered from")
    match_score: int = Field(..., description="Gemini ATS match score percentage (0-100)")
    status: str = Field(..., description="Pipeline triage status: Ready or Archived")
    recommendation: str = Field(..., description="AI Recommendation: Apply, Upskill, or Skip")
    resume_tex_path: Optional[str] = Field(default=None, description="Path to tailored LaTeX resume")
    resume_pdf_path: Optional[str] = Field(default=None, description="Path to compiled PDF resume")


class IngestionReport(BaseModel):
    """Aggregate summary of an autonomous discovery and ingestion run."""
    total_discovered: int = 0
    duplicates_skipped: int = 0
    high_matches_ready: int = 0
    low_matches_archived: int = 0
    errors_count: int = 0
    auto_applied_count: int = 0
    jobs: List[IngestionJobResult] = []


async def ingest_single_job(
    discovered: DiscoveredJob,
    min_match_score: int = READY_MATCH_THRESHOLD,
    profile_path: str = str(DEFAULT_PROFILE_PATH),
) -> Optional[IngestionJobResult]:
    """
    Ingests, scores, and auto-triages a single discovered job.
    Routes high-match jobs (>= min_match_score) to Resume Tailoring & Outreach,
    and auto-archives low-match jobs (< min_match_score).
    """
    db = SessionLocal()
    try:
        # 1. Final deduplication check
        if job_exists(db, job_url=discovered.job_url, title=discovered.title, company=discovered.company):
            logger.info(f"Skipping duplicate job: {discovered.title} at {discovered.company}")
            return None

        # 2. Guarantee robust description text for Gemini analysis
        jd_text = discovered.description.strip()
        if len(jd_text) < 40:
            jd_text = (
                f"Role: {discovered.title}\n"
                f"Company: {discovered.company}\n"
                f"Location: {discovered.location}\n"
                f"Salary/Terms: {discovered.salary}\n"
                f"URL: {discovered.job_url}\n"
                f"Description: Opportunity for {discovered.title} at {discovered.company} in {discovered.location}."
            )

        # Upfront Expiry Pre-Check: Drop expired / closed jobs before LLM scoring & DB storage
        jd_lower = (jd_text or "").lower()
        expiry_markers = [
            "this job has expired",
            "job has expired",
            "this job is no longer active",
            "job is no longer available",
            "this job is no longer accepting applications",
            "position has been filled",
            "this vacancy has expired",
            "this vacancy has been filled",
            "job has been closed by employer",
            "this listing has expired",
            "this job posting has expired",
            "we are no longer accepting responses",
        ]
        if any(marker in jd_lower for marker in expiry_markers):
            logger.info(f"🚫 EXPIRED JOB PRE-FILTER: '{discovered.title}' at '{discovered.company}' is expired. Discarded immediately before LLM!")
            emit_event("discovery", "discovery_progress", {
                "stage": "expired_skip",
                "title": discovered.title,
                "company": discovered.company,
                "portal": discovered.portal,
                "message": f"🚫 Skipped expired job: '{discovered.title}' at {discovered.company}"
            })
            return None

        # 3. Evaluate ATS Match Score via Claude Haiku (Phase 1 AI Brain)
        logger.info(f"Scoring Job with Claude Haiku: '{discovered.title}' at '{discovered.company}'...")
        emit_event("discovery", "discovery_progress", {
            "stage": "evaluating",
            "title": discovered.title,
            "company": discovered.company,
            "portal": discovered.portal,
            "message": f"Evaluating ATS match fit with Claude Haiku for '{discovered.title}' at {discovered.company}..."
        })
        match_result = await asyncio.to_thread(
            analyze_and_score_job,
            job_description=jd_text,
            profile_path=profile_path,
            title=discovered.title,
            company=discovered.company,
            portal=discovered.portal,
            job_url=discovered.job_url,
        )

        score = match_result.match_score
        tex_path = ""
        pdf_path = ""

        # 4. Strict Quality Filter: Drop jobs below READY_MATCH_THRESHOLD (70%)
        # Prevents database and UI clutter. Zero garbage saved.
        if score < min_match_score:
            logger.info(f"🗑️ LOW MATCH ({score}% < {min_match_score}%). Discarded '{discovered.title}' (Not saved to DB).")
            emit_event("discovery", "discovery_progress", {
                "stage": "scored",
                "title": discovered.title,
                "company": discovered.company,
                "portal": discovered.portal,
                "match_score": score,
                "status": "Discarded",
                "recommendation": match_result.recommendation,
                "message": f"Scored '{discovered.title}': {score}% (< {min_match_score}%) -> Discarded (Zero clutter)!"
            })
            return None

        # 5. Atomic Save: Only persist high-quality jobs (>= 70%) to SQLite
        job_record = create_job(
            db=db,
            job_title=discovered.title,
            company_name=discovered.company,
            job_description=jd_text,
            location=discovered.location,
            portal_name=discovered.portal,
            job_url=discovered.job_url,
            salary_range=discovered.salary,
        )
        save_job_evaluation(db, job_id=job_record.id, match=match_result)

        # Crawler-First Authority: The physical button detected on page has 100% supreme authority over LLM text reading
        crawler_apply_type = getattr(discovered, "apply_type", "1-Click")
        llm_apply_type = getattr(match_result, "apply_type", "1-Click")

        if crawler_apply_type == "Applied":
            final_apply_type = "Applied"
        elif crawler_apply_type == "1-Click":
            # Native 1-Click Apply button detected on Naukri - LLM text speculation CANNOT override physical reality
            final_apply_type = "1-Click"
        elif crawler_apply_type == "External":
            final_apply_type = "External"
        else:
            final_apply_type = llm_apply_type or "1-Click"

        discovered.apply_type = final_apply_type

        logger.info(
            f"🧠 Brain+Hand Classification for '{discovered.title}' at '{discovered.company}': "
            f"LLM Brain={llm_apply_type} (Reason: {getattr(match_result, 'apply_type_reasoning', '')}) | "
            f"Agent Hand={crawler_apply_type} -> Final='{final_apply_type}'"
        )

        if final_apply_type == "Applied":
            target_status = "Applied"
            status_note = f"Application confirmed submitted on {discovered.portal.title()}."
            logger.info(f"✅ ALREADY APPLIED on {discovered.portal.title()}. Triaged directly to Applied.")
        elif final_apply_type == "External":
            target_status = "Ready" if score >= AUTO_APPLY_MATCH_THRESHOLD else "Archived"
            reason = getattr(match_result, "apply_type_reasoning", "")
            reason_suffix = f" ({reason})" if reason else ""
            status_note = f"External Company Portal: Direct employer application required on {discovered.portal.title()}{reason_suffix}."
            logger.info(f"🌐 EXTERNAL PORTAL on {discovered.portal.title()}{reason_suffix}. Triaged to {target_status} with External tag.")
        elif score >= AUTO_APPLY_MATCH_THRESHOLD:
            target_status = "Ready"
            status_note = f"1-Click Apply Ready: Elite ATS match {score}% (≥{AUTO_APPLY_MATCH_THRESHOLD}%). In Review queue for 1-Click apply."
            logger.info(f"⭐ ELITE MATCH ({score}% >= {AUTO_APPLY_MATCH_THRESHOLD}%). Added to Review queue (Ready)...")
        else:
            target_status = "Archived"
            status_note = f"1-Click Apply Ready: Solid ATS match {score}% (70-{AUTO_APPLY_MATCH_THRESHOLD-1}%). Stored in Reserve Pool (Archived)."
            logger.info(f"📁 SOLID MATCH ({score}% in 70-{AUTO_APPLY_MATCH_THRESHOLD-1}%). Stored in Reserve Pool (Archived)...")

        master_pdf = Path(__file__).resolve().parent.parent.parent / "data" / "uploaded_resume.pdf"
        pdf_path = str(master_pdf) if master_pdf.exists() else ""
        tex_path = ""

        create_or_update_application(
            db=db,
            job_id=job_record.id,
            status=target_status,
            tex_path=tex_path,
            pdf_path=pdf_path,
            cold_subject="",
            cold_body="",
            linkedin_note="",
            notes=status_note,
        )
        maintain_top_active_jobs(db=db)

        emit_event("discovery", "discovery_progress", {
            "stage": "scored",
            "job_id": job_record.id,
            "title": discovered.title,
            "company": discovered.company,
            "portal": discovered.portal,
            "match_score": score,
            "status": target_status,
            "recommendation": match_result.recommendation,
            "message": f"Scored '{discovered.title}': {score}% match -> Auto-triaged to {target_status}!"
        })

        return IngestionJobResult(
            job_id=job_record.id,
            title=discovered.title,
            company=discovered.company,
            portal=discovered.portal,
            match_score=score,
            status=target_status,
            recommendation=match_result.recommendation,
            resume_tex_path=tex_path or None,
            resume_pdf_path=pdf_path or None,
        )

    except Exception as e:
        logger.error(f"Error ingesting job '{discovered.title}' at '{discovered.company}': {e}", exc_info=True)
        return None
    finally:
        db.close()


async def run_autonomous_ingestion(
    discovered_jobs: List[DiscoveredJob],
    min_match_score: int = READY_MATCH_THRESHOLD,
    max_jobs_to_process: int = 5,
    profile_path: str = str(DEFAULT_PROFILE_PATH),
) -> IngestionReport:
    """
    Ingests a batch of discovered jobs up to max_jobs_to_process,
    respecting Gemini rate limits and returning a structured report.
    """
    report = IngestionReport(total_discovered=len(discovered_jobs))

    to_process = discovered_jobs[:max_jobs_to_process]
    logger.info(f"Starting autonomous ingestion pipeline for {len(to_process)} job(s)...")

    for discovered in to_process:
        try:
            result = await ingest_single_job(
                discovered=discovered,
                min_match_score=min_match_score,
                profile_path=profile_path,
            )

            if result is None:
                report.duplicates_skipped += 1
            else:
                report.jobs.append(result)
                if result.status == "Ready":
                    report.high_matches_ready += 1
                elif result.status == "Archived":
                    report.low_matches_archived += 1

        except Exception as e:
            logger.error(f"Ingestion worker error on {discovered.title}: {e}")
            report.errors_count += 1

    logger.info(
        f"Ingestion completed: {report.high_matches_ready} Ready, "
        f"{report.low_matches_archived} Archived, {report.duplicates_skipped} Duplicates skipped."
    )
    return report


async def process_1click_applications(max_daily_limit: int = 7, min_score: int = AUTO_APPLY_MATCH_THRESHOLD):
    """
    Autonomous 1-Click Apply Worker:
    Inspects qualifying jobs in the Review queue ('Ready' status).
    - Checks whether each job is a native 1-Click Apply on Naukri OR an External Company Site link.
    - If Native 1-Click Apply: Agent automatically clicks Apply in the backend (zero human clicks needed)!
    - If External Company Site link: Skips applying for now, marks notes, leaves in Review.
    - Stops as soon as the daily limit (7) is reached. Leftover jobs remain in Review for tomorrow!
    """
    from app.agent.applier import EasyApplyFiller
    from app.agent.scorer import load_profile

    try:
        profile = load_profile()
        max_daily = getattr(profile.preferences, "autopilot_max_daily_apps", max_daily_limit) or max_daily_limit
        threshold_score = getattr(profile.preferences, "autopilot_auto_apply_score", min_score) or min_score
    except Exception:
        max_daily = max_daily_limit
        threshold_score = min_score

    applied_in_this_run = 0
    filler = EasyApplyFiller(headless=True)

    with SessionLocal() as db:
        applied_today = crud.get_applied_today_count(db)
        logger.info(f"📊 Auto-Apply quota check: {applied_today}/{max_daily} applications submitted today.")

        if applied_today >= max_daily:
            logger.info(f"Daily safety quota reached ({applied_today}/{max_daily}). Leftover jobs stay in Review for tomorrow.")
            emit_event("autopilot", "quota_reached", {"applied_today": applied_today, "max_daily": max_daily})
            return {"applied_count": 0, "daily_total": applied_today, "status": "QUOTA_FULL"}

        ready_jobs = crud.list_jobs(db=db, limit=50, status="Ready")
        candidates = [
            j for j in ready_jobs
            if (j.evaluation and j.evaluation.match_score >= threshold_score)
            and "External Company Portal" not in (j.applications[0].notes if j.applications else "")
            and j.job_url
        ]

        if not candidates:
            logger.info("No unapplied 1-Click candidate jobs in Review queue.")
            return {"applied_count": 0, "daily_total": applied_today, "status": "EMPTY"}

        logger.info(f"⚡ Autonomous Agent inspecting {len(candidates)} jobs in Review queue for 1-Click Apply...")
        emit_event("discovery", "discovery_progress", {
            "stage": "applying",
            "message": f"Autonomous Agent inspecting {len(candidates)} jobs for 1-Click Apply (Daily Limit: {applied_today}/{max_daily})..."
        })

        for job in candidates:
            if applied_today >= max_daily:
                logger.info(f"Daily safety quota reached ({applied_today}/{max_daily}). Leftover jobs stay in Review for tomorrow.")
                emit_event("autopilot", "quota_reached", {"applied_today": applied_today, "max_daily": max_daily})
                break

            score = job.evaluation.match_score if job.evaluation else 0
            pdf_path = job.applications[0].tailored_resume_pdf_path if job.applications else None

            portal_display = "Indeed" if ("indeed.com" in (job.job_url or "").lower() or (job.portal_name or "").lower() == "indeed") else "Naukri"
            logger.info(f"🔍 Backend Agent inspecting '{job.job_title}' at '{job.company_name}' for 1-Click vs External Site on {portal_display}...")
            try:
                res = await asyncio.to_thread(
                    filler.fill_and_stage_application,
                    target_url_or_path=job.job_url,
                    resume_path=pdf_path,
                    job_title=job.job_title,
                    company_name=job.company_name,
                    thread_id=f"auto_{job.id}_{int(asyncio.get_event_loop().time())}",
                    auto_submit=True
                )

                if res.status == "SUBMITTED":
                    crud.create_or_update_application(
                        db=db,
                        job_id=job.id,
                        status="Applied",
                        notes=f"Auto-applied autonomously via 1-Click Apply on {portal_display} (Score: {score}%)."
                    )
                    applied_today += 1
                    applied_in_this_run += 1
                    logger.info(f"✅ Successfully auto-applied to '{job.job_title}' at '{job.company_name}' on {portal_display} ({applied_today}/{max_daily} today).")
                    emit_event("discovery", "discovery_progress", {
                        "stage": "applied",
                        "job_id": job.id,
                        "title": job.job_title,
                        "company": job.company_name,
                        "portal": portal_display,
                        "message": f"✅ Auto-applied to '{job.job_title}' at {job.company_name} via {portal_display} ({applied_today}/{max_daily})!"
                    })

                elif res.status == "ALREADY_APPLIED":
                    crud.create_or_update_application(
                        db=db,
                        job_id=job.id,
                        status="Applied",
                        notes=f"Already applied on {portal_display}."
                    )
                    logger.info(f"ℹ️ Already applied to '{job.job_title}' at '{job.company_name}' on {portal_display}. Marked Applied.")

                elif res.status == "EXTERNAL_SITE":
                    ext_status = "Ready" if score >= AUTO_APPLY_MATCH_THRESHOLD else "Archived"
                    ext_note = (
                        f"External Company Portal: Direct employer application required on {portal_display}."
                        if score >= AUTO_APPLY_MATCH_THRESHOLD
                        else f"External Company Portal on {portal_display}: ({score}% in Reserve Pool)."
                    )
                    crud.create_or_update_application(
                        db=db,
                        job_id=job.id,
                        status=ext_status,
                        notes=ext_note
                    )
                    logger.info(f"🔗 '{job.job_title}' at '{job.company_name}' redirects to external company portal. Triaged to {ext_status}.")
                    emit_event("discovery", "discovery_progress", {
                        "stage": "external_skip",
                        "job_id": job.id,
                        "title": job.job_title,
                        "company": job.company_name,
                        "portal": portal_display,
                        "message": f"🔗 '{job.job_title}' at {job.company_name} is an external portal -> Triaged to {ext_status}."
                    })

                elif res.status == "LOGIN_REQUIRED":
                    logger.warning(f"{portal_display} login session is disconnected. Halting auto-apply.")
                    emit_event("discovery", "discovery_progress", {
                        "stage": "auth_warning",
                        "message": f"{portal_display} login session disconnected. Please click 'Launch Safe Login Session' in Settings."
                    })
                    break

            except Exception as apply_err:
                logger.warning(f"Error during auto-apply for job {job.id}: {apply_err}")

    return {
        "applied_count": applied_in_this_run,
        "daily_total": applied_today,
        "max_daily": max_daily,
        "status": "COMPLETED"
    }


async def discover_and_ingest(
    search_term: Optional[str] = None,
    search_terms: Optional[List[str]] = None,
    location: Optional[str] = None,
    locations: Optional[List[str]] = None,
    portals: Optional[List[str]] = None,
    results_wanted: int = 10,
    freshness_days: int = 1,
    experience_level: Optional[str] = None,
    min_match_score: int = READY_MATCH_THRESHOLD,
    max_jobs_to_process: int = 5,
) -> IngestionReport:
    """
    End-to-end autonomous discovery and ingestion pipeline.
    Discovers fresh listings across portals, deduplicates, evaluates with Claude Haiku,
    and populates SQLite jobs.db. Thread-safe with concurrency lock.
    """
    if _discovery_lock.locked():
        logger.warning("Discovery cycle already active in another thread/task. Skipping overlapping trigger.")
        return IngestionReport(
            total_discovered=0,
            duplicates_skipped=0,
            high_matches_ready=0,
            low_matches_archived=0,
            errors_count=0,
            auto_applied_count=0,
            jobs=[]
        )

    async with _discovery_lock:
        prefs = load_candidate_preferences()
        saved_exp = prefs.get("experience_level", "0-1")
        eff_exp = experience_level if experience_level is not None else saved_exp
        exp_labels = {"0-1": "Fresher (0-1 Yrs)", "1-2": "Early Career (1-2 Yrs)", "2-4": "Associate (2-4 Yrs)", "all": "Any Exp"}
        exp_label = exp_labels.get(eff_exp, eff_exp)

        if search_terms and len(search_terms) > 0:
            term_str = ", ".join(search_terms[:3])
        elif search_term and search_term.strip():
            term_str = search_term.strip()
        else:
            try:
                saved = prefs.get("target_roles", [])
                term_str = ", ".join(saved[:3]) if saved else "AI Engineer / Python"
            except Exception:
                term_str = "AI Engineer / Python"

        if locations and len(locations) > 0:
            loc_str = ", ".join(locations[:2])
        elif location and location.strip():
            loc_str = location.strip()
        else:
            try:
                saved_locs = prefs.get("preferred_locations", [])
                loc_str = ", ".join(saved_locs[:2]) if saved_locs else "Hyderabad"
            except Exception:
                loc_str = "Hyderabad"

        effective_portals = portals or ["naukri"]
        portal_names = ", ".join([p.title() for p in effective_portals])
        freshness_label = f"Past {freshness_days * 24} Hours" if freshness_days == 1 else (f"Past {freshness_days} Days" if freshness_days > 0 else "All Time")

        emit_event("discovery", "discovery_progress", {
            "stage": "scraping",
            "search_term": term_str,
            "location": loc_str,
            "portals": effective_portals,
            "freshness": freshness_label,
            "experience": exp_label,
            "message": f"Searching {portal_names} in parallel for '{term_str}' in '{loc_str}' ({freshness_label}, {exp_label})..."
        })

        logger.info(f"Triggering parallel end-to-end discovery across {portal_names} for '{term_str}' in '{loc_str}' ({freshness_label}, exp={exp_label})...")
        raw_discovered = await discover_jobs(
            search_term=search_term,
            search_terms=search_terms,
            location=location,
            locations=locations,
            portals=effective_portals,
            results_per_portal=results_wanted,
            freshness_days=freshness_days,
            experience_level=eff_exp,
            deduplicate=True,
        )

        emit_event("discovery", "discovery_progress", {
            "stage": "discovered",
            "count": len(raw_discovered),
            "message": f"Found {len(raw_discovered)} live postings. Evaluating fit and deduplicating with SQLite..."
        })

        report = await run_autonomous_ingestion(
            discovered_jobs=raw_discovered,
            min_match_score=min_match_score,
            max_jobs_to_process=max_jobs_to_process,
        )

        # Autonomously trigger 1-Click apply on elite matches (>= 80%, respecting daily max 7)
        try:
            apply_res = await process_1click_applications(min_score=AUTO_APPLY_MATCH_THRESHOLD)
            report.auto_applied_count = apply_res.get("applied_count", 0)
        except Exception as app_err:
            logger.error(f"Error executing autonomous 1-click apply: {app_err}")

        emit_event("discovery", "discovery_progress", {
            "stage": "completed",
            "total_discovered": report.total_discovered,
            "high_matches_ready": report.high_matches_ready,
            "low_matches_archived": report.low_matches_archived,
            "duplicates_skipped": report.duplicates_skipped,
            "auto_applied_count": report.auto_applied_count,
            "message": f"Discovery complete! {report.auto_applied_count} auto-applied via 1-Click. Remaining high matches queued in Review for tomorrow."
        })

        return report
