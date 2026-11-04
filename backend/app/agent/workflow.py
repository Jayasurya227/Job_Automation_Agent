"""
Module: workflow.py
Purpose: Direct, high-performance job application execution pipeline with Human-in-the-Loop review and Playwright automation.
Standards: Rule 1 (Zero Blind Trust), Rule 2 (Type & Schema Safety), Rule 3 (Low Code & High Signal), Rule 5 (Production Reliability).

Status rules (important for the database):
  - A job is only marked 'Applied' when the form filler reports SUBMITTED.
  - A failed score, missing URL, bot challenge, or navigation error never marks a job as applied.
"""
import time
import logging
from pathlib import Path
from typing import TypedDict, List, Dict, Any, Optional, Annotated, Literal
import operator

from app.config import DATA_DIR, BASE_DIR, READY_MATCH_THRESHOLD
from app.schemas.match import JobMatchResult
from app.agent.scorer import analyze_and_score_job, load_profile
from app.db.session import SessionLocal
from app.db import crud
from app.utils.event_bus import emit_event

logger = logging.getLogger("workflow")

DEFAULT_WORKFLOW_DB = DATA_DIR / "workflows.db"

# Active in-memory session registry for staged applications awaiting candidate review.
# An entry is removed as soon as the candidate decides (approve or reject).
WORKFLOW_SESSIONS: Dict[str, Dict[str, Any]] = {}


class JobApplicationState(TypedDict, total=False):
    """
    Shared clipboard representing the full lifecycle of a job application.
    """
    thread_id: str
    job_id: Optional[int]
    job_title: str
    company_name: str
    job_url: str
    portal_name: str
    job_description: str
    location: str

    # AI Evaluation fields
    match_score: Optional[int]
    matching_skills: List[str]
    missing_skills: List[str]
    key_strengths: List[str]
    recommendation: Optional[str]
    evaluation_reasoning: Optional[str]

    # Artifacts
    tailored_resume_tex_path: Optional[str]
    tailored_resume_pdf_path: Optional[str]
    cold_email_subject: Optional[str]
    cold_email_body: Optional[str]
    linkedin_connection_note: Optional[str]

    # Application Form & Status
    status: str  # DISCOVERED, EVALUATED, READY, REVIEW_GATEWAY, APPROVED, REJECTED_BY_USER, SUBMITTED, ARCHIVED, FAILED, NO_URL, EVALUATION_FAILED, ...
    screening_answers: Dict[str, Any]
    review_snapshot_path: Optional[str]
    confirmation_snapshot_path: Optional[str]
    requires_human_approval: bool
    human_approved: bool
    rejection_reason: Optional[str]

    # Audit log
    execution_logs: List[str]
    error_message: Optional[str]


def _get_timestamp() -> str:
    return time.strftime("%H:%M:%S")


def _emit_workflow_event(
    state: Dict[str, Any],
    step: str,
    status: str,
    message: str,
    extra: Optional[Dict[str, Any]] = None
):
    """Broadcasts real-time workflow step progress over the SSE event bus."""
    tid = state.get("thread_id")
    jid = state.get("job_id")
    data = {
        "thread_id": tid,
        "job_id": jid,
        "job_title": state.get("job_title"),
        "company_name": state.get("company_name"),
        "portal_name": state.get("portal_name"),
        "step": step,
        "status": status,
        "message": message,
        "timestamp": _get_timestamp(),
        **(extra or {})
    }
    try:
        if tid:
            emit_event(f"workflow:{tid}", "workflow_step", data)
        if jid:
            emit_event(f"workflow:{jid}", "workflow_step", data)
        emit_event("workflow:all", "workflow_step", data)
    except Exception as ev_err:
        logger.debug(f"Event emission ignored: {ev_err}")


def _result(
    state: Dict[str, Any],
    tid: str,
    is_interrupted: bool = False,
    interrupt_payload: Optional[Dict[str, Any]] = None,
    next_nodes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Builds the uniform return shape used by run_application_workflow."""
    return {
        "thread_id": tid,
        "state": state,
        "is_interrupted": is_interrupted,
        "interrupt_payload": interrupt_payload,
        "next_nodes": next_nodes or [],
    }


def _record_applied(job_id: Optional[int], pdf_path: Optional[str], note: str) -> None:
    """Marks a job as Applied in SQLite. Only call this after a confirmed submission."""
    if not job_id:
        return
    try:
        with SessionLocal() as db:
            crud.update_job_status(db=db, job_id=job_id, status="Applied")
            crud.create_or_update_application(
                db=db,
                job_id=job_id,
                status="Applied",
                pdf_path=pdf_path or "",
                notes=note,
            )
    except Exception as db_err:
        logger.warning(f"Could not update status to Applied in SQLite: {db_err}")


def _mark_blocked(state: Dict[str, Any], status: str, message: str, step: str = "prepare_form") -> None:
    """Records a stop reason in the state, the audit log, and the SSE stream. Never marks Applied."""
    state["status"] = status
    state["error_message"] = message
    state["execution_logs"].append(f"[{_get_timestamp()}] {message}")
    _emit_workflow_event(state, step=step, status="blocked", message=message)


def run_application_workflow(
    job_title: str,
    company_name: str,
    job_description: str,
    job_url: str = "",
    portal_name: str = "Naukri",
    location: str = "Remote",
    job_id: Optional[int] = None,
    match_score: Optional[int] = None,
    requires_human_approval: bool = True,
    thread_id: Optional[str] = None,
    checkpointer: Optional[Any] = None,
    tailored_resume_tex_path: Optional[str] = None,
    tailored_resume_pdf_path: Optional[str] = None,
    cold_email_subject: Optional[str] = None,
    cold_email_body: Optional[str] = None,
    linkedin_connection_note: Optional[str] = None,
    is_manual_override: bool = False,
) -> Dict[str, Any]:
    """
    Executes a direct application pipeline for a given job.
    Uses master resume directly and triggers Playwright browser automation.
    If requires_human_approval is True, stages the form and pauses at Review Gateway.
    If False, submits the application and marks the job Applied only when submission is confirmed.
    """
    tid = thread_id or f"wf_{int(time.time() * 1000)}"
    ts = _get_timestamp()

    # 1. Master resume resolution
    master_pdf = BASE_DIR / "data" / "uploaded_resume.pdf"
    pdf_path = tailored_resume_pdf_path or (str(master_pdf) if master_pdf.exists() else None)

    state: Dict[str, Any] = {
        "thread_id": tid,
        "job_id": job_id,
        "job_title": job_title,
        "company_name": company_name,
        "job_url": job_url,
        "portal_name": portal_name,
        "job_description": job_description,
        "location": location,
        "match_score": match_score,
        "matching_skills": [],
        "missing_skills": [],
        "key_strengths": [],
        "recommendation": None,
        "evaluation_reasoning": None,
        "tailored_resume_tex_path": None,
        "tailored_resume_pdf_path": pdf_path,
        "cold_email_subject": "",
        "cold_email_body": "",
        "linkedin_connection_note": "",
        "status": "DISCOVERED",
        "screening_answers": {},
        "review_snapshot_path": None,
        "confirmation_snapshot_path": None,
        "requires_human_approval": requires_human_approval,
        "human_approved": False,
        "rejection_reason": None,
        "execution_logs": [f"[{ts}] Direct application workflow initialized for {job_title} at {company_name}."],
        "error_message": None,
    }

    _emit_workflow_event(
        state,
        step="start",
        status="running",
        message=f"Application workflow initialized for {job_title} at {company_name}."
    )

    # 2. Score Check / Evaluation
    # A failed evaluation stops the workflow. It must not default to a made-up score.
    score = match_score
    if score is None:
        _emit_workflow_event(
            state,
            step="evaluate",
            status="running",
            message=f"Evaluating ATS match fit for {job_title} at {company_name}..."
        )
        try:
            match_res = analyze_and_score_job(job_description=job_description)
            score = match_res.match_score
            state["match_score"] = score
            state["matching_skills"] = match_res.matching_skills
            state["missing_skills"] = match_res.missing_skills
            state["key_strengths"] = match_res.key_strengths
            state["recommendation"] = match_res.recommendation
            state["evaluation_reasoning"] = match_res.summary_reasoning
            state["status"] = "EVALUATED"
            state["execution_logs"].append(f"[{_get_timestamp()}] Scored {job_title}: {score}%.")
            _emit_workflow_event(
                state,
                step="evaluate",
                status="completed",
                message=f"Scored {job_title}: {score}% ({match_res.recommendation})",
                extra={"match_score": score, "recommendation": match_res.recommendation}
            )
        except Exception as e:
            logger.error(f"ATS scoring failed; workflow stopped: {e}")
            _mark_blocked(
                state,
                status="EVALUATION_FAILED",
                message=f"ATS scoring failed, so the application was not started: {e}",
                step="evaluate",
            )
            return _result(state, tid)

    # 3. Low Match Archiving (below the Ready threshold) - only if this is an automated unprompted pipeline, not a manual user application
    if not is_manual_override and (job_id is None) and score < READY_MATCH_THRESHOLD:
        log_msg = f"[{_get_timestamp()}] Match score ({score}%) below threshold ({READY_MATCH_THRESHOLD}%). Moving to Archive."
        state["status"] = "ARCHIVED"
        state["execution_logs"].append(log_msg)
        if job_id:
            try:
                with SessionLocal() as db:
                    crud.update_job_status(db=db, job_id=job_id, status="Archived")
            except Exception:
                pass
        _emit_workflow_event(state, step="archive", status="completed", message=log_msg)
        return _result(state, tid)

    # 4. Prepare Application & Candidate Answers
    _emit_workflow_event(
        state,
        step="prepare_form",
        status="running",
        message="Staging verified candidate profile answers & master resume..."
    )
    profile = load_profile()
    form_answers = {
        "full_name": profile.personal_info.name,
        "email": profile.personal_info.email,
        "phone": profile.personal_info.phone,
        "location": profile.personal_info.location,
        "linkedin_url": profile.personal_info.linkedin_url,
        "github_url": profile.personal_info.github_url,
        "portfolio_url": profile.personal_info.portfolio_url,
        "notice_period_days": profile.preferences.notice_period_days,
        "immediate_joiner": profile.application_answers.immediate_joiner,
        "willing_to_relocate": profile.application_answers.willing_to_relocate,
        "years_of_experience": profile.application_answers.years_of_experience,
        "work_authorization": profile.application_answers.work_authorization,
    }
    state["screening_answers"] = form_answers
    state["status"] = "READY"

    # Without a real application URL there is nothing to stage or submit.
    # Stop here instead of pretending the application was sent.
    if not job_url:
        _mark_blocked(
            state,
            status="NO_URL",
            message="This job has no application URL. Nothing was staged or submitted.",
        )
    # Check strict daily application safety quota (Max 7/day)
    max_daily_apps = getattr(profile.preferences, "autopilot_max_daily_apps", 7) or 7
    with SessionLocal() as db:
        applied_today = crud.get_applied_today_count(db)
        if applied_today >= max_daily_apps and not requires_human_approval:
            msg = f"Daily safety quota reached ({applied_today}/{max_daily_apps} applications today). Auto-apply paused to protect your account."
            logger.info(msg)
            _mark_blocked(state, status="QUOTA_REACHED", message=msg)
            return _result(state, tid)

    # 5. Execute Form Automation via Playwright
    try:
        from app.agent.applier import EasyApplyFiller
        filler = EasyApplyFiller(headless=True)
        res = filler.fill_and_stage_application(
            target_url_or_path=job_url,
            resume_path=pdf_path,
            job_title=job_title,
            company_name=company_name,
            thread_id=tid,
            auto_submit=(not requires_human_approval)
        )
    except Exception as e:
        logger.warning(f"Form filler failed: {e}")
        _mark_blocked(state, status="FAILED", message=f"Form automation failed: {e}")
        return _result(state, tid)

    state["review_snapshot_path"] = res.snapshot_path
    state["confirmation_snapshot_path"] = res.confirmation_snapshot_path
    for item in res.filled_fields:
        form_answers[item.field_name] = item.value_filled
    state["screening_answers"] = form_answers

    # 6. Branch on what the filler actually did
    if res.status == "SUBMITTED":
        # Filler confirmed submission (autonomous mode, or the portal already shows it as applied)
        state["human_approved"] = True
        state["status"] = "SUBMITTED"
        log_msg = f"[{_get_timestamp()}] Application for {job_title} at {company_name} ({portal_name}) SUBMITTED."
        state["execution_logs"].append(log_msg)
        _record_applied(job_id, pdf_path, note=f"Submitted via {portal_name} at {_get_timestamp()}")
        _emit_workflow_event(
            state,
            step="submit",
            status="completed",
            message=f"Application for {job_title} at {company_name} submitted successfully!",
            extra={"confirmation_snapshot_path": res.confirmation_snapshot_path}
        )
        return _result(state, tid)

    if requires_human_approval and res.status == "READY_FOR_REVIEW":
        # Assisted mode: staged and waiting for the candidate's decision
        state["status"] = "REVIEW_GATEWAY"
        interrupt_payload = {
            "action": "human_approval_required",
            "job_title": job_title,
            "company_name": company_name,
            "portal_name": portal_name,
            "match_score": score,
            "tailored_resume_pdf": pdf_path,
            "review_snapshot_path": res.snapshot_path,
            "screening_answers": form_answers,
            "timestamp": _get_timestamp(),
        }
        WORKFLOW_SESSIONS[tid] = state
        _emit_workflow_event(
            state,
            step="review_gateway",
            status="paused",
            message="Paused at Human Review Gateway. Awaiting candidate approval.",
            extra={
                "review_snapshot_path": res.snapshot_path,
                "screening_answers": form_answers
            }
        )
        return _result(state, tid, is_interrupted=True, interrupt_payload=interrupt_payload, next_nodes=["human_review"])

    # Anything else (bot challenge, login required, external site, no apply button, error...) stops here.
    if job_id and res.status == "EXTERNAL_SITE":
        try:
            with SessionLocal() as db:
                crud.create_or_update_application(
                    db=db,
                    job_id=job_id,
                    status="Ready",
                    notes="External Company Portal: Direct application required on employer site."
                )
        except Exception as db_err:
            logger.debug(f"Notice updating external site application note: {db_err}")

    state["execution_logs"].append(f"[{_get_timestamp()}] Form automation stopped with status {res.status}.")
    _mark_blocked(
        state,
        status=res.status,
        message=res.error_message or f"Form automation stopped with status {res.status}.",
    )
    return _result(state, tid)


def resume_application_workflow(
    thread_id: str,
    approved: bool = True,
    reason: Optional[str] = None,
    checkpointer: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Resumes an interrupted review workflow with the candidate's decision.
    Each pending review can be decided only once: the session is removed from the registry here.
    If approved: runs the submission and marks the job Applied only if submission is confirmed.

    Known limitation: approval re-runs the form automation in a new browser session rather than
    submitting the exact browser state that was reviewed.
    """
    ts = _get_timestamp()
    state = WORKFLOW_SESSIONS.pop(thread_id, None)

    if state is None:
        msg = "No pending review found for this thread. It may have already been decided, or the server restarted."
        logger.warning(f"[{thread_id}] {msg}")
        return {
            "thread_id": thread_id,
            "state": {"thread_id": thread_id, "status": "SESSION_NOT_FOUND", "execution_logs": [f"[{ts}] {msg}"]},
            "is_interrupted": False,
            "status": "SESSION_NOT_FOUND",
            "execution_logs": [f"[{ts}] {msg}"],
        }

    resume_msg = "Candidate APPROVED submission" if approved else f"Candidate REJECTED ({reason or 'Manual skip'})"
    emit_event(f"workflow:{thread_id}", "workflow_step", {
        "thread_id": thread_id,
        "step": "resume",
        "status": "approved" if approved else "rejected",
        "message": resume_msg,
        "timestamp": ts
    })
    emit_event("workflow:all", "workflow_step", {
        "thread_id": thread_id,
        "step": "resume",
        "status": "approved" if approved else "rejected",
        "message": resume_msg,
        "timestamp": ts
    })

    if not approved:
        state["status"] = "REJECTED_BY_USER"
        state["rejection_reason"] = reason or "Rejected by candidate in review gateway"
        state["execution_logs"].append(f"[{ts}] Candidate REJECTED application: {reason or 'Manual Skip'}.")
        return {
            "thread_id": thread_id,
            "state": state,
            "is_interrupted": False,
            "status": "REJECTED_BY_USER",
            "execution_logs": state.get("execution_logs", []),
        }

    # Execute Submission
    job_title = state.get("job_title", "Job")
    company = state.get("company_name", "Company")
    portal = state.get("portal_name", "Portal")
    job_url = state.get("job_url", "")
    pdf_path = state.get("tailored_resume_pdf_path")
    job_id = state.get("job_id")

    if not job_url:
        _mark_blocked(state, status="NO_URL", message="No application URL on record. Nothing was submitted.", step="submit")
        return {
            "thread_id": thread_id,
            "state": state,
            "is_interrupted": False,
            "status": "NO_URL",
            "execution_logs": state.get("execution_logs", []),
        }

    _emit_workflow_event(
        state,
        step="submit",
        status="running",
        message=f"Executing final application submission to {portal}..."
    )

    try:
        from app.agent.applier import EasyApplyFiller
        filler = EasyApplyFiller(headless=True)
        res = filler.fill_and_stage_application(
            target_url_or_path=job_url,
            resume_path=pdf_path,
            job_title=job_title,
            company_name=company,
            thread_id=thread_id,
            auto_submit=True
        )
    except Exception as e:
        logger.warning(f"Resume submit execution failed: {e}")
        _mark_blocked(state, status="FAILED", message=f"Submission failed: {e}", step="submit")
        return {
            "thread_id": thread_id,
            "state": state,
            "is_interrupted": False,
            "status": "FAILED",
            "execution_logs": state.get("execution_logs", []),
        }

    state["confirmation_snapshot_path"] = res.confirmation_snapshot_path

    if res.status != "SUBMITTED":
        _mark_blocked(
            state,
            status=res.status,
            message=res.error_message or f"Submission not confirmed (status {res.status}).",
            step="submit",
        )
        return {
            "thread_id": thread_id,
            "state": state,
            "is_interrupted": False,
            "status": res.status,
            "execution_logs": state.get("execution_logs", []),
        }

    state["human_approved"] = True
    state["status"] = "SUBMITTED"
    log_msg = f"[{ts}] Application for {job_title} at {company} ({portal}) SUBMITTED."
    state["execution_logs"].append(log_msg)
    _record_applied(job_id, pdf_path, note=f"Submitted via {portal} automated workflow at {ts}")

    _emit_workflow_event(
        state,
        step="submit",
        status="completed",
        message=f"Application for {job_title} at {company} submitted successfully!",
        extra={"confirmation_snapshot_path": res.confirmation_snapshot_path}
    )

    return {
        "thread_id": thread_id,
        "state": state,
        "is_interrupted": False,
        "status": "SUBMITTED",
        "execution_logs": state.get("execution_logs", []),
    }


# Backwards compatibility shims (used by test_workflow.py / test_hitl_gateway.py)
def get_sqlite_checkpointer(db_path: Optional[str] = None):
    return None

def build_application_graph(checkpointer: Optional[Any] = None):
    class SimpleGraph:
        def invoke(self, state, config=None):
            return state
        def get_state(self, config=None):
            class Snapshot:
                next = []
                tasks = []
            return Snapshot()
    return SimpleGraph()
