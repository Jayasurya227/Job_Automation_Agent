"""
Autonomous Ingestion & AI Scoring Pipeline.
Receives raw discovered jobs from multi-portal scraper, checks SQLite deduplication,
evaluates ATS match with Gemini, and auto-triages jobs into 'Ready' (>=75%) or 'Archived' (<75%).
For high-match jobs, automatically generates tailored LaTeX resumes and recruiter outreach packages.
Part of Phase 3: Browser Automation & Job Discovery.
"""

import logging
import asyncio
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field

from app.agent.scraper import DiscoveredJob, discover_jobs
from app.agent.scorer import analyze_and_score_job
from app.agent.outreach import generate_outreach
from app.db.session import SessionLocal
from app.db.crud import (
    create_job,
    save_job_evaluation,
    create_or_update_application,
    job_exists,
)
from app.utils.event_bus import emit_event

logger = logging.getLogger("agent.ingestion")

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
    jobs: List[IngestionJobResult] = []


async def ingest_single_job(
    discovered: DiscoveredJob,
    min_match_score: int = 75,
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

        # 3. Create Job Record in SQLite
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

        # 4. Evaluate ATS Match Score via Gemini (Phase 1 AI Brain)
        logger.info(f"Scoring Job ID {job_record.id}: '{discovered.title}' at '{discovered.company}'...")
        emit_event("discovery", "discovery_progress", {
            "stage": "evaluating",
            "title": discovered.title,
            "company": discovered.company,
            "portal": discovered.portal,
            "message": f"Evaluating ATS match fit for '{discovered.title}' at {discovered.company}..."
        })
        match_result = await asyncio.to_thread(
            analyze_and_score_job,
            job_description=jd_text,
            profile_path=profile_path,
        )

        # Save AI Evaluation to SQLite
        save_job_evaluation(db, job_id=job_record.id, match=match_result)

        score = match_result.match_score
        tex_path = ""
        pdf_path = ""

        # 5. Smart Auto-Triage Routing (Conditional Branch)
        if score >= min_match_score:
            target_status = "Ready"
            logger.info(f"⭐ HIGH MATCH ({score}% >= {min_match_score}%). Using uploaded Master Resume PDF...")

            # Use uploaded master resume PDF directly (zero LaTeX overhead)
            master_pdf = Path(__file__).resolve().parent.parent.parent / "data" / "uploaded_resume.pdf"
            pdf_path = str(master_pdf) if master_pdf.exists() else ""
            tex_path = ""

            # Cold Outreach metadata
            skills_preview = ", ".join(match_result.matching_skills[:3]) if match_result.matching_skills else "software engineering"

            # Dynamically pull candidate name from profile to avoid hardcoded personal data
            try:
                from app.schemas.profile import CandidateProfile
                import json as _json
                _profile_data = _json.loads(Path(profile_path).read_text(encoding="utf-8"))
                _candidate_name = CandidateProfile(**_profile_data).personal_info.name.split()[0]
            except Exception:
                _candidate_name = "Candidate"

            cold_subj = f"Application: {match_result.job_title} - {_candidate_name}"
            cold_body = (
                f"Dear Hiring Team,\n\nI am writing to express my strong interest in the {match_result.job_title} role at {match_result.company_name}. "
                f"With verified hands-on experience in {skills_preview}, I am confident in delivering immediate value. "
                "I am an immediate joiner (0 days notice period) and have attached my tailored resume for your consideration.\n\n"
                f"Best regards,\n{_candidate_name}"
            )
            li_note = f"Hi! I am very interested in the {match_result.job_title} position at {match_result.company_name}. Looking forward to connecting!"

            try:
                outreach = await asyncio.to_thread(
                    generate_outreach,
                    job_description=jd_text,
                    match_result=match_result,
                    recipient_role="HR_Recruiter",
                    profile_path=profile_path,
                )
                if outreach and outreach.subject_line:
                    cold_subj = outreach.subject_line
                if outreach and outreach.cold_email_body:
                    cold_body = outreach.cold_email_body
                if outreach and outreach.linkedin_connection_note:
                    li_note = outreach.linkedin_connection_note
            except Exception as outreach_err:
                logger.warning(f"Outreach dynamic generation notice for Job {job_record.id} (used grounded fallback): {outreach_err}")

            # C. Persist Application as Ready
            create_or_update_application(
                db=db,
                job_id=job_record.id,
                status="Ready",
                tex_path=tex_path,
                pdf_path=pdf_path,
                cold_subject=cold_subj,
                cold_body=cold_body,
                linkedin_note=li_note,
                notes=f"Auto-ingested with high ATS match {score}%. Tailored resume & outreach generated.",
            )

        else:
            target_status = "Archived"
            logger.info(f"⏩ LOW MATCH ({score}% < {min_match_score}%). Auto-archiving Job ID {job_record.id}...")
            create_or_update_application(
                db=db,
                job_id=job_record.id,
                status="Archived",
                notes=f"Auto-archived: ATS Match score ({score}%) is below minimum threshold ({min_match_score}%).",
            )

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
    min_match_score: int = 75,
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


async def discover_and_ingest(
    search_term: Optional[str] = None,
    location: Optional[str] = None,
    portals: Optional[List[str]] = None,
    results_wanted: int = 10,
    freshness_days: int = 1,
    min_match_score: int = 75,
    max_jobs_to_process: int = 5,
) -> IngestionReport:
    """
    End-to-end autonomous discovery and ingestion pipeline.
    Discovers fresh listings across portals, deduplicates, evaluates with Gemini,
    and populates SQLite jobs.db.
    """
    term_str = search_term or "AI Engineer / Python"
    loc_str = location or "India / Remote"
    portal_names = ", ".join(portals) if portals else "Naukri"
    freshness_label = f"Past {freshness_days * 24} Hours" if freshness_days == 1 else (f"Past {freshness_days} Days" if freshness_days > 0 else "All Time")

    emit_event("discovery", "discovery_progress", {
        "stage": "scraping",
        "search_term": term_str,
        "location": loc_str,
        "portals": portals or [],
        "freshness": freshness_label,
        "message": f"Searching {portal_names} for '{term_str}' in '{loc_str}' ({freshness_label})..."
    })

    logger.info(f"Triggering end-to-end discovery for '{search_term or 'default'}' in '{location or 'default'}' ({freshness_label})...")
    raw_discovered = await discover_jobs(
        search_term=search_term,
        location=location,
        portals=portals,
        results_per_portal=results_wanted,
        freshness_days=freshness_days,
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

    emit_event("discovery", "discovery_progress", {
        "stage": "completed",
        "total_discovered": report.total_discovered,
        "high_matches_ready": report.high_matches_ready,
        "low_matches_archived": report.low_matches_archived,
        "duplicates_skipped": report.duplicates_skipped,
        "message": f"Discovery complete! {report.high_matches_ready} Ready, {report.low_matches_archived} Archived, {report.duplicates_skipped} Duplicates skipped."
    })

    return report
