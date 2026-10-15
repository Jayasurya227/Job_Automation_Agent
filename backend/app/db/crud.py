"""
Module: crud.py
Purpose: Database CRUD operations for Jobs, Evaluations, Application Tracker, and Q&A.
Standards: Rule 1 (ACID Transactions), Rule 2 (Type Integrity), Rule 3 (Concise & Efficient).
"""
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
try:
    from app.db.models import Job, JobEvaluation, Application, ApplicationAnswer
    from app.schemas.match import JobMatchResult
except ImportError:
    from .models import Job, JobEvaluation, Application, ApplicationAnswer
    from ..schemas.match import JobMatchResult

def create_job(
    db: Session,
    job_title: str,
    company_name: str,
    job_description: str,
    location: str = "",
    portal_name: str = "Manual",
    job_url: str = "",
    salary_range: str = ""
) -> Job:
    """Inserts a new job listing into the database."""
    job = Job(
        job_title=job_title.strip(),
        company_name=company_name.strip(),
        job_description=job_description.strip(),
        location=location.strip(),
        portal_name=portal_name.strip(),
        job_url=job_url.strip(),
        salary_range=salary_range.strip()
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job

def job_exists(db: Session, job_url: str = "", title: str = "", company: str = "") -> bool:
    """Checks whether a job already exists in SQLite by URL or normalized (title + company)."""
    if job_url and job_url.strip():
        existing_url = db.query(Job.id).filter(Job.job_url == job_url.strip()).first()
        if existing_url:
            return True

    if title and company:
        existing_tc = db.query(Job.id).filter(
            Job.job_title.ilike(title.strip()),
            Job.company_name.ilike(company.strip())
        ).first()
        if existing_tc:
            return True

    return False

def get_job(db: Session, job_id: int) -> Optional[Job]:
    """Retrieves a single job with its evaluation and applications."""
    return db.query(Job).filter(Job.id == job_id).first()

def list_jobs(db: Session, skip: int = 0, limit: int = 100, status: Optional[str] = None) -> List[Job]:
    """Retrieves all jobs, optionally filtering by application pipeline status."""
    query = db.query(Job)
    if status:
        query = query.join(Job.applications).filter(Application.status == status)
    return query.order_by(Job.created_at.desc()).offset(skip).limit(limit).all()

def save_job_evaluation(db: Session, job_id: int, match: JobMatchResult) -> JobEvaluation:
    """Saves or updates the AI match evaluation for a job."""
    eval_record = db.query(JobEvaluation).filter(JobEvaluation.job_id == job_id).first()
    if not eval_record:
        eval_record = JobEvaluation(job_id=job_id)
        db.add(eval_record)
    
    eval_record.match_score = match.match_score
    eval_record.recommendation = match.recommendation
    eval_record.matching_skills = match.matching_skills
    eval_record.missing_skills = match.missing_skills
    eval_record.key_strengths = match.key_strengths
    eval_record.reasoning = match.summary_reasoning
    eval_record.evaluated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(eval_record)
    return eval_record

def create_or_update_application(
    db: Session,
    job_id: int,
    status: str = "Saved",
    tex_path: str = "",
    pdf_path: str = "",
    cold_subject: str = "",
    cold_body: str = "",
    linkedin_note: str = "",
    notes: str = ""
) -> Application:
    """Creates or updates tracking data for a job application."""
    app_record = db.query(Application).filter(Application.job_id == job_id).first()
    if not app_record:
        app_record = Application(job_id=job_id)
        db.add(app_record)

    app_record.status = status
    if tex_path:
        app_record.tailored_resume_tex_path = tex_path
    if pdf_path:
        app_record.tailored_resume_pdf_path = pdf_path
    if cold_subject:
        app_record.cold_email_subject = cold_subject
    if cold_body:
        app_record.cold_email_body = cold_body
    if linkedin_note:
        app_record.linkedin_note = linkedin_note
    if notes:
        app_record.notes = notes

    if status == "Applied" and not app_record.applied_at:
        app_record.applied_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(app_record)
    return app_record

def update_application_status(db: Session, application_id: int, new_status: str) -> Optional[Application]:
    """Updates the pipeline status for an existing application."""
    app_record = db.query(Application).filter(Application.id == application_id).first()
    if not app_record:
        return None
    app_record.status = new_status
    if new_status == "Applied" and not app_record.applied_at:
        app_record.applied_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(app_record)
    return app_record

def update_job_status(db: Session, job_id: int, status: str) -> Application:
    """Updates or creates the application status record for a job."""
    return create_or_update_application(db=db, job_id=job_id, status=status)

def delete_job(db: Session, job_id: int) -> bool:
    """Deletes a job and cascades deletion to its evaluation and application records."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        return False
    db.delete(job)
    db.commit()
    return True

def save_qa_answer(db: Session, question: str, answer: str, category: str = "General") -> ApplicationAnswer:
    """Saves or updates a screening question and verified candidate answer."""
    qa = db.query(ApplicationAnswer).filter(ApplicationAnswer.question == question.strip()).first()
    if not qa:
        qa = ApplicationAnswer(question=question.strip())
        db.add(qa)
    qa.answer = answer.strip()
    qa.category = category.strip()
    db.commit()
    db.refresh(qa)
    return qa

def get_qa_answer(db: Session, question: str) -> Optional[ApplicationAnswer]:
    """Finds exact match for question in Q&A bank."""
    return db.query(ApplicationAnswer).filter(ApplicationAnswer.question == question.strip()).first()

def list_qa_answers(db: Session) -> List[ApplicationAnswer]:
    """Returns all cached screening questions and answers."""
    return db.query(ApplicationAnswer).all()


# =====================================================================
# Sub-Phase 5.3: Analytics, Funnel Calculations & Performance Metrics
# =====================================================================

def get_detailed_analytics(db: Session) -> dict:
    """
    Computes comprehensive analytics across the entire job application lifecycle:
    - Funnel stage transitions and conversion percentages
    - Application velocity (past 24h, 7d, 30d)
    - Source portal distribution
    - High-frequency matching skills and missing skill gap alerts
    - Real-time audit activity feed
    """
    jobs = db.query(Job).all()
    total_jobs = len(jobs)

    status_counts = {
        "Saved": 0,
        "Tailored": 0,
        "Applied": 0,
        "Interview": 0,
        "Offer": 0,
        "Rejected": 0,
        "Archived": 0
    }
    portal_counts: dict[str, int] = {}
    matching_skills_counter: dict[str, int] = {}
    missing_skills_counter: dict[str, int] = {}
    scores: List[int] = []

    now = datetime.now(timezone.utc)
    applied_today = 0
    applied_this_week = 0
    applied_this_month = 0
    activity_timeline = []

    for j in jobs:
        # Portal breakdown
        raw_portal = j.portal_name or "Manual"
        portal_name = raw_portal.strip().title()
        portal_counts[portal_name] = portal_counts.get(portal_name, 0) + 1

        # Match evaluations
        if j.evaluation:
            score = j.evaluation.match_score
            scores.append(score)

            # Aggregate matching skills
            for s in (j.evaluation.matching_skills or []):
                s_clean = str(s).strip()
                if s_clean:
                    matching_skills_counter[s_clean] = matching_skills_counter.get(s_clean, 0) + 1

            # Aggregate missing skills
            for s in (j.evaluation.missing_skills or []):
                s_clean = str(s).strip()
                if s_clean:
                    missing_skills_counter[s_clean] = missing_skills_counter.get(s_clean, 0) + 1

        # Application status & velocity
        app_rec = j.applications[0] if j.applications else None
        app_status = app_rec.status if app_rec else "Saved"
        if app_status in status_counts:
            status_counts[app_status] += 1
        else:
            status_counts[app_status] = status_counts.get(app_status, 0) + 1

        # Velocity check
        if app_rec and app_rec.applied_at:
            applied_time = app_rec.applied_at
            if applied_time.tzinfo is None:
                applied_time = applied_time.replace(tzinfo=timezone.utc)
            delta = (now - applied_time).total_seconds()
            if delta <= 86400:
                applied_today += 1
            if delta <= 7 * 86400:
                applied_this_week += 1
            if delta <= 30 * 86400:
                applied_this_month += 1

        # Activity timeline item
        activity_timestamp = (app_rec.applied_at or j.created_at) if app_rec else j.created_at
        if activity_timestamp and activity_timestamp.tzinfo is None:
            activity_timestamp = activity_timestamp.replace(tzinfo=timezone.utc)

        activity_timeline.append({
            "job_id": j.id,
            "job_title": j.job_title,
            "company_name": j.company_name,
            "portal_name": portal_name,
            "status": app_status,
            "match_score": j.evaluation.match_score if j.evaluation else None,
            "timestamp": activity_timestamp.isoformat() if activity_timestamp else None
        })

    # Sort activity by newest first
    activity_timeline.sort(key=lambda x: x["timestamp"] or "", reverse=True)
    recent_activity = activity_timeline[:12]

    # Funnel conversions
    applied_count = status_counts.get("Applied", 0) + status_counts.get("Interview", 0) + status_counts.get("Offer", 0)
    interview_count = status_counts.get("Interview", 0) + status_counts.get("Offer", 0)
    offer_count = status_counts.get("Offer", 0)

    conversion_rates = {
        "apply_rate": round((applied_count / total_jobs * 100), 1) if total_jobs > 0 else 0.0,
        "interview_rate": round((interview_count / applied_count * 100), 1) if applied_count > 0 else 0.0,
        "offer_rate": round((offer_count / interview_count * 100), 1) if interview_count > 0 else 0.0,
    }

    # Top skills
    top_matching = sorted(
        [{"skill": k, "count": v} for k, v in matching_skills_counter.items()],
        key=lambda x: x["count"],
        reverse=True
    )[:8]
    top_missing = sorted(
        [{"skill": k, "count": v} for k, v in missing_skills_counter.items()],
        key=lambda x: x["count"],
        reverse=True
    )[:8]

    # Portal distribution
    portals_summary = sorted(
        [
            {
                "portal": k,
                "count": v,
                "percentage": round((v / total_jobs * 100), 1) if total_jobs > 0 else 0.0
            }
            for k, v in portal_counts.items()
        ],
        key=lambda x: x["count"],
        reverse=True
    )

    # Score tiers
    high_match = sum(1 for s in scores if s >= 80)
    med_match = sum(1 for s in scores if 60 <= s < 80)
    low_match = sum(1 for s in scores if s < 60)
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0

    return {
        "summary": {
            "total_jobs": total_jobs,
            "average_match_score": avg_score,
            "ready_to_apply_count": status_counts.get("Tailored", 0),
            "applied_count": applied_count,
            "interview_count": interview_count,
            "offer_count": offer_count,
            "archived_count": status_counts.get("Archived", 0),
            "rejected_count": status_counts.get("Rejected", 0),
        },
        "velocity": {
            "applied_today": applied_today,
            "applied_this_week": applied_this_week,
            "applied_this_month": applied_this_month,
        },
        "conversion_rates": conversion_rates,
        "score_distribution": {
            "high_match": high_match,
            "viable_match": med_match,
            "low_match": low_match,
            "total_evaluated": len(scores),
        },
        "portals": portals_summary,
        "skills_insights": {
            "top_matching_skills": top_matching,
            "top_missing_skills": top_missing,
        },
        "recent_activity": recent_activity
    }

