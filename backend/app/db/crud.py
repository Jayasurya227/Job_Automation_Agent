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
    """
    Checks whether a job already exists in SQLite:
    1. If the candidate has already APPLIED, NEVER re-discover or re-apply (permanent safety).
    2. If previously discovered/unapplied, checks within the 30-day window to prevent duplicate listings.
    """
    from datetime import timedelta
    cutoff_30d = datetime.utcnow() - timedelta(days=30)

    # 1. Check by URL
    if job_url and job_url.strip():
        url_clean = job_url.strip()
        matching_jobs = db.query(Job).filter(Job.job_url == url_clean).all()
        for j in matching_jobs:
            if any(app.status == "Applied" for app in j.applications):
                return True  # Already applied - never duplicate
            if j.created_at and j.created_at >= cutoff_30d:
                return True  # Within 30 days - skip duplicate

    # 2. Check by Title + Company
    if title and company:
        t_clean = title.strip()
        c_clean = company.strip()
        matching_tc = db.query(Job).filter(
            Job.job_title.ilike(t_clean),
            Job.company_name.ilike(c_clean)
        ).all()
        for j in matching_tc:
            if any(app.status == "Applied" for app in j.applications):
                return True  # Already applied - never duplicate
            if j.created_at and j.created_at >= cutoff_30d:
                return True  # Within 30 days - skip duplicate

    return False

def get_job(db: Session, job_id: int) -> Optional[Job]:
    """Retrieves a single job with its evaluation and applications."""
    return db.query(Job).filter(Job.id == job_id).first()

def list_jobs(
    db: Session, 
    skip: int = 0, 
    limit: int = 100, 
    status: Optional[str] = None,
    days_limit: Optional[int] = None
) -> List[Job]:
    """
    Retrieves jobs, optionally filtering by pipeline status and rolling days limit (e.g. 7-day rolling window).
    """
    query = db.query(Job)
    if status:
        query = query.join(Job.applications).filter(Application.status == status)
    if days_limit is not None and days_limit > 0:
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=days_limit)
        # Include jobs created within rolling window OR applied within rolling window
        query = query.outerjoin(Job.applications).filter(
            (Job.created_at >= cutoff) | (Application.applied_at >= cutoff)
        ).distinct()
    return query.order_by(Job.created_at.desc()).offset(skip).limit(limit).all()

def get_jobs_history(
    db: Session,
    year: Optional[int] = None,
    month: Optional[int] = None
) -> dict:
    """
    Retrieves historical jobs grouped into Discovered and Applied for a specific month and year,
    along with available months metadata.
    """
    import calendar
    now = datetime.utcnow()
    target_year = year if year is not None else now.year
    target_month = month if month is not None else now.month

    all_jobs = db.query(Job).order_by(Job.created_at.desc()).all()

    # Extract available months from all jobs in database
    months_map = {}
    for j in all_jobs:
        app_rec = j.applications[0] if j.applications else None
        ref_date = (app_rec.applied_at if app_rec and app_rec.applied_at else j.created_at) or now
        key = (ref_date.year, ref_date.month)
        months_map[key] = months_map.get(key, 0) + 1

    # Ensure current month is always present in available list even if 0 jobs
    current_key = (now.year, now.month)
    if current_key not in months_map:
        months_map[current_key] = 0

    available_months = []
    for (y, m) in sorted(months_map.keys(), reverse=True):
        m_name = calendar.month_name[m]
        available_months.append({
            "year": y,
            "month": m,
            "label": f"{m_name} {y}",
            "count": months_map[(y, m)]
        })

    # Filter jobs for target_year and target_month
    discovered_list = []
    applied_list = []

    for j in all_jobs:
        ev = j.evaluation
        app_rec = j.applications[0] if j.applications else None
        is_applied = (app_rec is not None and app_rec.status == "Applied")

        # Date used for grouping: applied_at for applied jobs, created_at for discovered jobs
        job_date = (app_rec.applied_at if is_applied and app_rec.applied_at else j.created_at) or now

        if job_date.year == target_year and job_date.month == target_month:
            item = {
                "id": j.id,
                "job_title": j.job_title,
                "company_name": j.company_name,
                "location": j.location,
                "portal_name": j.portal_name,
                "job_url": j.job_url,
                "salary_range": j.salary_range,
                "match_score": ev.match_score if ev else None,
                "recommendation": ev.recommendation if ev else None,
                "status": app_rec.status if app_rec else "Saved",
                "applied_at": app_rec.applied_at.isoformat() if app_rec and app_rec.applied_at else None,
                "created_at": j.created_at.isoformat() if j.created_at else None,
                "notes": app_rec.notes if app_rec else "",
            }
            if is_applied:
                applied_list.append(item)
            else:
                discovered_list.append(item)

    month_label = f"{calendar.month_name[target_month]} {target_year}"

    return {
        "year": target_year,
        "month": target_month,
        "month_name": month_label,
        "discovered_count": len(discovered_list),
        "applied_count": len(applied_list),
        "total_count": len(discovered_list) + len(applied_list),
        "discovered_jobs": discovered_list,
        "applied_jobs": applied_list,
        "available_months": available_months,
    }

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

def maintain_top_active_jobs(db: Session, max_active: int = 3):
    """
    No-op: All high-matching jobs remain in active status ('Ready' / 'Review')
    so that the candidate can see all opportunities and the daily quota can process them in order.
    """
    pass

def refill_top_active_jobs(db: Session, max_active: int = 3):
    """
    No-op: Active jobs remain in their natural pipeline stages.
    """
    pass

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

    if status in ["Ready", "Saved"]:
        maintain_top_active_jobs(db, max_active=3)
    elif status in ["Applied", "Archived"]:
        refill_top_active_jobs(db, max_active=3)

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

    # If an application moved away from Ready, refill Top 3 from reserve
    if new_status in ["Applied", "Archived"]:
        refill_top_active_jobs(db, max_active=3)

    return app_record

def update_job_status(db: Session, job_id: int, status: str) -> Application:
    """Updates or creates the application status record for a job."""
    res = create_or_update_application(db=db, job_id=job_id, status=status)
    if status in ["Applied", "Archived"]:
        refill_top_active_jobs(db, max_active=3)
    return res

def delete_job(db: Session, job_id: int) -> bool:
    """Deletes a job and cascades deletion to its evaluation and application records."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        return False
    db.delete(job)
    db.commit()
    refill_top_active_jobs(db, max_active=3)
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
            if applied_time.tzinfo is not None:
                local_app_time = applied_time.astimezone()
            else:
                local_app_time = applied_time.replace(tzinfo=timezone.utc).astimezone()

            if local_app_time.date() == datetime.now().date():
                applied_today += 1

            if applied_time.tzinfo is None:
                applied_time = applied_time.replace(tzinfo=timezone.utc)
            delta = (now - applied_time).total_seconds()
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


def get_applied_today_count(db: Session, target_date: Optional[datetime] = None) -> int:
    """
    Returns the total number of applications submitted today (current local calendar day since 00:00:00).
    Resets cleanly at midnight so that each new day starts with a fresh 0 count.
    """
    now_local = target_date or datetime.now()
    today_date = now_local.date()
    count = 0
    apps = db.query(Application).filter(Application.status == "Applied").all()
    for app in apps:
        if app.applied_at:
            app_time = app.applied_at
            if app_time.tzinfo is not None:
                local_app_time = app_time.astimezone()
            else:
                local_app_time = app_time.replace(tzinfo=timezone.utc).astimezone()

            if local_app_time.date() == today_date:
                count += 1
    return count


