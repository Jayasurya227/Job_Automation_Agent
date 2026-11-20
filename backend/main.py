"""
Module: main.py
Purpose: Step 2.2 FastAPI Backend Server - Central API connecting AI Brain, Database, and Dashboard.
Standards: Rule 1 (Zero Blind Trust), Rule 2 (Strict Pydantic Validation & Locked CORS),
           Rule 3 (Low Code & High Accuracy), Rule 4 (Standard Layout), Rule 5 (Production Reliability).
"""
import sys
import json
import asyncio
import logging
import os
import re
import secrets

# Ensure Windows ProactorEventLoop is used so Playwright child processes don't raise NotImplementedError
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Literal, cast, Annotated
from fastapi import FastAPI, Depends, HTTPException, Query, status, Request, File, UploadFile
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

logger = logging.getLogger("main")

from app.config import CORS_ORIGINS, CORS_ALLOW_ALL, OUTPUT_DIR, BASE_DIR, READY_MATCH_THRESHOLD
from app.db.session import init_db, get_db
from app.db.models import User
from app.core.security import get_current_user, get_optional_current_user, get_current_user_from_token_or_header

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[Optional[User], Depends(get_optional_current_user)]
CurrentUserOrQuery = Annotated[User, Depends(get_current_user_from_token_or_header)]

from app.db import crud
from app.routers.auth import router as auth_router
from app.agent import scorer, outreach, discover_and_ingest, IngestionReport, qa_bank
from app.agent.workflow import run_application_workflow, resume_application_workflow, WORKFLOW_SESSIONS
from app.utils.event_bus import event_bus
from app.schemas.profile import CandidateProfile
from app.schemas.api import (
    AnalyzeJobRequest,
    AnalyzeJobResponse,
    UpdateStatusRequest,
    JobListItem,
    JobDetailResponse,
    PipelineMetrics,
    DiscoverJobsRequest,
    ApplyWorkflowRequest,
    ResumeWorkflowRequest,
    WorkflowStatusResponse,
    SaveQARequest,
    QAItemResponse,
    UpdateAccountSettingsRequest,
    NaukriMobileConnectRequest,
    NaukriVerifyOtpRequest,
    NaukriCancelSessionRequest,
    NaukriConnectResponse,
    IndeedMobileConnectRequest,
    IndeedVerifyOtpRequest,
    IndeedCancelSessionRequest,
    IndeedConnectResponse,
)
from app.agent.headless_auth import headless_auth_manager
from app.agent.mailer import (
    load_account_settings,
    save_account_settings,
    get_masked_settings,
    PortalAccountConfig,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes SQLite database tables and registers main event loop with EventBus and AutoPilot."""
    init_db()
    if not _API_TOKEN:
        logger.warning("API_TOKEN is not set: the API accepts requests without authentication. Set API_TOKEN in backend/.env to lock it down.")
    try:
        loop = asyncio.get_running_loop()
        event_bus.set_event_loop(loop)
        from app.agent.scheduler import autopilot_scheduler
        autopilot_scheduler.start()
    except Exception as e:
        logger.warning(f"Lifespan initialization notice: {e}")
    yield
    try:
        from app.agent.scheduler import autopilot_scheduler
        autopilot_scheduler.stop()
        from app.agent.task_queue import task_queue
        await task_queue.stop()
    except Exception:
        pass

app = FastAPI(
    title="Autonomous Job Automation Agent API",
    description="Production REST API powering autonomous job discovery, ATS scoring, resume tailoring, and tracking.",
    version="1.0.0",
    lifespan=lifespan
)

# -------------------------------------------------------------------
# Optional API Token Middleware (Security Fix)
# Set API_TOKEN in backend/.env to enable token-based auth.
# If API_TOKEN is NOT set, the server remains open for local use (a warning is logged at startup).
# Clients must send: X-API-Token: <your-token>
# Browser-initiated requests that cannot set headers (EventSource SSE, file links, iframes)
# may pass the token as the ?api_token=<your-token> query parameter instead.
# Health check is always public so the frontend can detect server status.
# -------------------------------------------------------------------
_API_TOKEN: str = os.getenv("API_TOKEN", "")

@app.middleware("http")
async def optional_api_token_guard(request: Request, call_next):
    """If API_TOKEN env var is set, enforces token auth on all non-health routes."""
    if _API_TOKEN:
        # Always allow health check and OPTIONS (CORS preflight)
        skip_paths = {"/", "/api/health"}
        if request.method != "OPTIONS" and request.url.path not in skip_paths:
            client_token = request.headers.get("X-API-Token", "") or request.query_params.get("api_token", "")
            if not secrets.compare_digest(client_token, _API_TOKEN):
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Unauthorized: Invalid or missing X-API-Token header."}
                )
    return await call_next(request)

# Rule 2: Strict CORS Protection with Dynamic Cloud & local network support (Issue 11)
if CORS_ALLOW_ALL or "*" in CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)(:\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

@app.get("/output/snapshots/{filename}", tags=["Snapshots"])
def get_snapshot_file(
    filename: str,
    db: DbSession,
    token: Optional[str] = Query(None),
    current_user: OptionalUser = None,
):
    """
    Securely serves review and confirmation snapshot screenshots strictly scoped to the authenticated user.
    Prevents unauthorized access and cross-user data leakage.
    Supports either Bearer token in Authorization header or ?token=<jwt> query parameter for <img> tags.
    """
    resolved_user = current_user
    if not resolved_user and token:
        from app.core.security import get_current_user
        try:
            resolved_user = get_current_user(token=token, db=db)
        except Exception:
            resolved_user = None

    if not resolved_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required to view snapshots."
        )

    clean_filename = Path(filename).name
    if not clean_filename or clean_filename != filename:
        raise HTTPException(status_code=400, detail="Invalid snapshot filename.")

    from app.core.user_storage import get_user_snapshots_dir, USERS_ROOT_DIR

    # 1. Check user's own isolated snapshots vault
    user_snap_file = get_user_snapshots_dir(resolved_user.id) / clean_filename
    if user_snap_file.exists():
        return FileResponse(path=str(user_snap_file), media_type="image/png")

    # 2. Check legacy global snapshots (only for User 1)
    if resolved_user.id == 1:
        legacy_file = OUTPUT_DIR / "snapshots" / clean_filename
        if legacy_file.exists():
            return FileResponse(path=str(legacy_file), media_type="image/png")

    # 3. Check if file belongs to another user's vault (anti-snooping guard)
    if USERS_ROOT_DIR.exists():
        for user_folder in USERS_ROOT_DIR.iterdir():
            if user_folder.is_dir() and user_folder.name != str(resolved_user.id):
                other_snap = user_folder / "output" / "snapshots" / clean_filename
                if other_snap.exists():
                    logger.warning(
                        f"🚨 Anti-Snoop Guard: User {resolved_user.id} attempted to view User {user_folder.name}'s snapshot '{clean_filename}'!"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied: You do not have permission to view this snapshot."
                    )

    raise HTTPException(status_code=404, detail="Snapshot not found.")

# Note: Raw /output static directory mount removed to prevent unauthenticated access to candidate resumes.
# Snapshots are securely served via /output/snapshots/{filename} with strict JWT anti-snoop protection.
# Resumes are securely served via /api/profile/download-* and /api/jobs/{id}/tailored-resume-pdf endpoints.

# Include Authentication Router (Multi-Tenant Phase 1)
app.include_router(auth_router)

@app.get("/", tags=["Health"])
@app.get("/api/health", tags=["Health"])
def health_check():
    """System health check endpoint."""
    return {
        "status": "online",
        "agent": "Autonomous Job Automation Agent",
        "version": "1.0.0",
        "database": "SQLite (Connected)"
    }

@app.get("/api/events/stream", tags=["Events"])
async def stream_events(
    request: Request,
    topic: str = Query("all"),
    token: Optional[str] = Query(None, description="Optional JWT token for event stream authorization")
):
    """
    Sub-Phase 5.1: Real-Time Server-Sent Events (SSE) Stream with Anti-Eavesdropping Guard.
    Clients subscribe to real-time workflow, discovery, or system progress events.
    Supports topic filtering (e.g. topic=workflow:1, topic=discovery, or topic=all).
    Includes automatic 15-second heartbeat ping to prevent timeouts.
    """
    from fastapi.responses import JSONResponse
    from app.core.security import decode_access_token

    # Extract user identity from Authorization header or query param
    auth_header = request.headers.get("Authorization", "")
    jwt_str = token if isinstance(token, str) else None
    if not jwt_str and auth_header.startswith("Bearer "):
        jwt_str = auth_header.split(" ", 1)[1].strip()

    request_user_id = None
    if jwt_str:
        payload = decode_access_token(jwt_str)
        if payload and "sub" in payload:
            try:
                request_user_id = int(payload["sub"])
            except ValueError:
                pass

    # 1. Require valid authentication for all SSE event streams (Zero Eavesdropping)
    if request_user_id is None:
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication token required to subscribe to live event streams."}
        )

    # 2. Block un-scoped topics that could leak cross-tenant events
    clean_topic = topic.strip().lower()
    if clean_topic in ["autopilot", "discovery", "task"]:
        return JSONResponse(
            status_code=400,
            content={"detail": f"Please subscribe to your private user-scoped channel: {clean_topic}:{request_user_id}"}
        )

    # 3. User-scoped and Workflow anti-snooping authorization
    if ":" in topic:
        parts = topic.split(":", 1)
        channel_type = parts[0].lower()
        channel_target = parts[1].strip()

        if channel_type in ["autopilot", "discovery", "task", "user"]:
            if channel_target.isdigit():
                target_uid = int(channel_target)
                if request_user_id != target_uid:
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "Forbidden: Cannot subscribe to another user's live stream."}
                    )

        elif channel_type == "workflow":
            if channel_target.isdigit():
                job_id = int(channel_target)
                from app.db.session import SessionLocal
                from app.db import crud
                with SessionLocal() as db:
                    user_job = crud.get_job(db=db, job_id=job_id, user_id=request_user_id)
                    if not user_job:
                        return JSONResponse(
                            status_code=403,
                            content={"detail": "Forbidden: Cannot subscribe to workflow updates for a job you do not own."}
                        )
            elif channel_target == "all" and request_user_id != 1:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Forbidden: Cannot subscribe to global workflow channel."}
                )

    queue = await event_bus.subscribe(topic=topic)

    async def event_generator():
        # Immediately flush SSE connection handshake
        yield f": connected to topic {topic}\n\n"

        # First send any recent cached events so client gets immediate state
        recent = event_bus.get_recent_events(topic=topic)
        for ev in recent:
            payload = json.dumps(ev["data"])
            yield f"event: {ev['event']}\ndata: {payload}\n\n"

        try:
            while True:
                try:
                    # Wait up to 15s for new event; if timeout, send keep-alive ping
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    payload = json.dumps(event["data"])
                    yield f"event: {event['event']}\ndata: {payload}\n\n"
                except asyncio.TimeoutError:
                    # Heartbeat comment to keep connection alive
                    yield ": ping\n\n"
        except (asyncio.CancelledError, GeneratorExit):
            pass
        finally:
            await event_bus.unsubscribe(topic=topic, queue=queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            # CORS for SSE is handled by the CORSMiddleware above.
            # Do NOT override with wildcard here — that would bypass the strict CORS policy.
        }
    )

@app.post("/api/analyze", response_model=AnalyzeJobResponse, status_code=status.HTTP_201_CREATED, tags=["Agent Core"])
def analyze_job(req: AnalyzeJobRequest, db: DbSession, current_user: CurrentUser):
    """
    Unified Autonomous Pipeline Endpoint:
    1. AI Scorer evaluates match score and skills scoped to current_user.
    2. Saves Job and Evaluation to SQLite scoped to current_user.
    3. If score >= READY_MATCH_THRESHOLD, the job is marked Ready with the master resume attached.
    4. Saves Application tracking record to SQLite.
    """
    user_id = current_user.id

    # 1. AI ATS Scoring (Phase 1 AI Brain scoped to current_user)
    match_result = scorer.analyze_and_score_job(req.job_description, user_id=user_id)

    job_title = req.job_title.strip() if req.job_title else match_result.job_title
    company_name = req.company_name.strip() if req.company_name else match_result.company_name

    # 2. Persist Job to SQLite (Phase 2 Memory)
    job = crud.create_job(
        db=db,
        job_title=job_title,
        company_name=company_name,
        job_description=req.job_description,
        location=req.location or "",
        portal_name=req.portal_name or "Manual",
        job_url=req.job_url or "",
        salary_range=req.salary_range or "",
        user_id=user_id
    )

    # 3. Persist Evaluation to SQLite
    crud.save_job_evaluation(db=db, job_id=job.id, match=match_result)

    tex_path = ""
    pdf_path = None
    cold_subject = ""
    cold_body = ""
    linkedin_note = ""
    app_status = "Saved"

    # 4. Use master ATS resume for viable roles (score >= READY_MATCH_THRESHOLD)
    if match_result.match_score >= READY_MATCH_THRESHOLD:
        from app.core.user_storage import get_user_resume
        master_pdf = get_user_resume(user_id) if user_id else None
        pdf_path = str(master_pdf) if (master_pdf and master_pdf.exists()) else None
        cold_subject = ""
        cold_body = ""
        linkedin_note = ""
        app_status = "Ready"

    # 5. Persist Application Pipeline Tracking Record
    crud.create_or_update_application(
        db=db,
        job_id=job.id,
        status=app_status,
        tex_path=tex_path,
        pdf_path=pdf_path or "",
        cold_subject=cold_subject,
        cold_body=cold_body,
        linkedin_note=linkedin_note,
        user_id=user_id
    )

    return AnalyzeJobResponse(
        job_id=job.id,
        job_title=job.job_title,
        company_name=job.company_name,
        location=job.location,
        portal_name=job.portal_name,
        job_url=job.job_url,
        match_score=match_result.match_score,
        recommendation=match_result.recommendation,
        matching_skills=match_result.matching_skills,
        missing_skills=match_result.missing_skills,
        key_strengths=match_result.key_strengths,
        summary_reasoning=match_result.summary_reasoning,
        tailored_resume_tex_path=tex_path,
        tailored_resume_pdf_path=pdf_path,
        cold_email_subject=cold_subject,
        cold_email_body=cold_body,
        linkedin_note=linkedin_note,
        status=app_status
    )

@app.post("/api/discover", response_model=IngestionReport, tags=["Agent Core"])
async def trigger_job_discovery(req: DiscoverJobsRequest, current_user: CurrentUser):
    """
    Unified Multi-Portal Discovery & Autonomous Ingestion Endpoint (Phase 3):
    1. Scrapes fresh postings across requested portals (Naukri, Indeed).
    2. Smart deduplication filters out already-tracked jobs in SQLite for current_user.
    3. Gemini evaluates ATS match score.
    4. Auto-triages high matches (>= READY_MATCH_THRESHOLD) to 'Ready' with the master resume attached.
    5. Auto-triages low matches (below READY_MATCH_THRESHOLD) to 'Archived'.
    6. Returns structured IngestionReport scoped strictly to current_user.
    """
    user_id = current_user.id
    try:
        report = await discover_and_ingest(
            search_term=req.search_term,
            search_terms=req.search_terms,
            location=req.location,
            locations=req.locations,
            portals=req.portals,
            results_wanted=req.results_wanted,
            freshness_days=req.freshness_days if req.freshness_days is not None else 1,
            experience_level=req.experience_level,
            min_match_score=req.min_match_score,
            max_jobs_to_process=req.max_process,
            user_id=user_id,
        )
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Discovery engine error: {str(e)}")

@app.get("/api/jobs", response_model=List[JobListItem], tags=["Pipeline"])
def list_all_jobs(
    db: DbSession,
    current_user: CurrentUser,
    status_filter: Optional[str] = Query(None, alias="status"),
    days_limit: Optional[int] = Query(7, description="Rolling active window limit in days (default 7 days, 0 or null for all)"),
    skip: int = 0,
    limit: int = 100,
):
    """Retrieves tracked jobs from SQLite with rolling 7-day active filter, evaluations and pipeline status scoped strictly to current_user."""
    user_id = current_user.id
    effective_days = days_limit if (days_limit is not None and days_limit > 0) else None
    jobs = crud.list_jobs(db=db, skip=skip, limit=limit, status=status_filter, days_limit=effective_days, user_id=user_id)
    results = []
    for j in jobs:
        ev = j.evaluation
        app_rec = j.applications[0] if j.applications else None
        results.append(JobListItem(
            id=j.id,
            job_title=j.job_title,
            company_name=j.company_name,
            location=j.location,
            portal_name=j.portal_name,
            job_url=j.job_url,
            match_score=ev.match_score if ev else None,
            recommendation=ev.recommendation if ev else None,
            status=app_rec.status if app_rec else "Saved",
            tailored_resume_tex_path=app_rec.tailored_resume_tex_path if app_rec else "",
            tailored_resume_pdf_path=app_rec.tailored_resume_pdf_path if app_rec else None,
            applied_at=app_rec.applied_at.isoformat() if app_rec and app_rec.applied_at else None,
            notes=app_rec.notes if app_rec else None,
            created_at=j.created_at.isoformat()
        ))
    return results

@app.get("/api/jobs/history", tags=["Pipeline"])
def get_jobs_history(
    db: DbSession,
    current_user: CurrentUser,
    year: Optional[int] = Query(None, description="Filter history by 4-digit year (e.g. 2026)"),
    month: Optional[int] = Query(None, description="Filter history by month (1-12)"),
):
    """Retrieves full historical jobs categorized by month & year into Discovered and Applied scoped to current_user."""
    user_id = current_user.id
    return crud.get_jobs_history(db=db, year=year, month=month, user_id=user_id)

def _load_candidate_info(user_id: Optional[int] = None):
    """Returns the candidate's personal info from profile.json scoped to user_id, or an empty default if unavailable."""
    from app.schemas.profile import PersonalInfo
    from app.agent.scorer import load_profile
    try:
        return load_profile(user_id=user_id).personal_info
    except Exception:
        return PersonalInfo(name="Candidate")

@app.get("/api/jobs/{job_id}", response_model=JobDetailResponse, tags=["Pipeline"])
def get_job_detail(job_id: int, db: DbSession, current_user: CurrentUser):
    """Retrieves complete details for a single job including evaluation and application state scoped to current_user."""
    user_id = current_user.id
    job = crud.get_job(db=db, job_id=job_id, user_id=user_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    ev = job.evaluation
    app_rec = job.applications[0] if job.applications else None

    # Regex extract any recruiter email from job description
    detected_email = None
    if job.job_description:
        found_emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', job.job_description)
        valid_emails = [e for e in found_emails if not e.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'))]
        if valid_emails:
            detected_email = valid_emails[0]

    # Resolve master PDF resume path fallback scoped to user_id
    from app.core.user_storage import get_user_resume
    master_pdf = get_user_resume(user_id) if user_id else None
    pdf_path = (app_rec.tailored_resume_pdf_path if app_rec and app_rec.tailored_resume_pdf_path else "")
    if not pdf_path and master_pdf and master_pdf.exists():
        pdf_path = str(master_pdf)

    # Candidate identity comes from profile.json scoped to user_id
    candidate = _load_candidate_info(user_id=user_id)
    candidate_name = candidate.name

    cold_subj = (app_rec.cold_email_subject if app_rec and app_rec.cold_email_subject else f"Application: {job.job_title} - {candidate_name}")
    cold_body = (app_rec.cold_email_body if app_rec and app_rec.cold_email_body else (
        f"Dear Hiring Team,\n\n"
        f"I am writing to express my strong interest in the {job.job_title} position at {job.company_name}.\n\n"
        f"Please find my resume attached below for your review. I look forward to speaking with you.\n\n"
        f"Best regards,\n"
        f"{candidate_name}"
        + (f"\nPhone: {candidate.phone}" if candidate.phone else "")
    ))

    return JobDetailResponse(
        id=job.id,
        job_title=job.job_title,
        company_name=job.company_name,
        job_description=job.job_description,
        location=job.location,
        portal_name=job.portal_name,
        job_url=job.job_url,
        salary_range=job.salary_range,
        match_score=ev.match_score if ev else None,
        recommendation=ev.recommendation if ev else None,
        matching_skills=ev.matching_skills if ev and ev.matching_skills else [],
        missing_skills=ev.missing_skills if ev and ev.missing_skills else [],
        key_strengths=ev.key_strengths if ev and ev.key_strengths else [],
        summary_reasoning=ev.reasoning if ev else None,
        status=app_rec.status if app_rec else "Saved",
        tailored_resume_tex_path=app_rec.tailored_resume_tex_path if app_rec else "",
        tailored_resume_pdf_path=pdf_path or None,
        cold_email_subject=cold_subj,
        cold_email_body=cold_body,
        linkedin_note=app_rec.linkedin_note if app_rec else "",
        detected_email=detected_email,
        notes=app_rec.notes if app_rec else "",
        created_at=job.created_at.isoformat(),
        applied_at=app_rec.applied_at.isoformat() if app_rec and app_rec.applied_at else None
    )

@app.get("/api/jobs/{job_id}/resume", tags=["Pipeline"])
def get_job_resume(job_id: int, db: DbSession, current_user: CurrentUser):
    """Fetches the generated resume content and download paths scoped to current_user."""
    user_id = current_user.id
    job = crud.get_job(db=db, job_id=job_id, user_id=user_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    app_rec = job.applications[0] if job.applications else None
    if not app_rec or not app_rec.tailored_resume_tex_path:
        raise HTTPException(status_code=404, detail="No tailored resume found for this job")
    
    tex_path = Path(app_rec.tailored_resume_tex_path)
    tex_content = ""
    if tex_path.exists():
        with open(tex_path, "r", encoding="utf-8") as f:
            tex_content = f.read()

    return {
        "job_id": job.id,
        "tex_path": str(tex_path).replace("\\", "/"),
        "pdf_path": str(app_rec.tailored_resume_pdf_path).replace("\\", "/") if app_rec.tailored_resume_pdf_path else None,
        "tex_content": tex_content
    }

@app.patch("/api/jobs/{job_id}/status", tags=["Pipeline"])
def update_job_status(job_id: int, req: UpdateStatusRequest, db: DbSession, current_user: CurrentUser):
    """Updates application pipeline status scoped to current_user."""
    user_id = current_user.id
    job = crud.get_job(db=db, job_id=job_id, user_id=user_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    app_rec = crud.create_or_update_application(db=db, job_id=job.id, status=req.status, notes=req.notes or "", user_id=user_id)
    return {"status": "success", "job_id": job.id, "new_status": app_rec.status}

@app.delete("/api/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Pipeline"])
def delete_tracked_job(job_id: int, db: DbSession, current_user: CurrentUser):
    """Deletes a job and cascades deletion to all associated evaluations and application data scoped to current_user."""
    user_id = current_user.id
    deleted = crud.delete_job(db=db, job_id=job_id, user_id=user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Job not found")
    return None

@app.get("/api/metrics", response_model=PipelineMetrics, tags=["Dashboard"])
def get_pipeline_metrics(db: DbSession, current_user: CurrentUser):
    """Calculates live metrics for the dashboard cards scoped strictly to current_user (active 7-day rolling window)."""
    user_id = current_user.id
    jobs = crud.list_jobs(db=db, skip=0, limit=1000, days_limit=7, user_id=user_id)
    total = len(jobs)
    scores = [j.evaluation.match_score for j in jobs if j.evaluation]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0

    applied_count = sum(1 for j in jobs if j.applications and j.applications[0].status == "Applied")
    interview_count = sum(1 for j in jobs if j.applications and j.applications[0].status == "Interview")
    offer_count = sum(1 for j in jobs if j.applications and j.applications[0].status == "Offer")
    ready_count = sum(1 for j in jobs if j.applications and j.applications[0].status == "Ready")
    applied_today = crud.get_applied_today_count(db, user_id=user_id)

    max_daily = 7
    try:
        from app.agent.scorer import load_profile
        p = load_profile(user_id=user_id)
        max_daily = getattr(p.preferences, "autopilot_max_daily_apps", 7) or 7
    except Exception:
        pass

    return PipelineMetrics(
        total_jobs=total,
        average_match_score=avg_score,
        ready_to_apply_count=ready_count,
        applied_count=applied_count,
        applied_today=applied_today,
        max_daily_apps=max_daily,
        interview_count=interview_count,
        offer_count=offer_count
    )


@app.get("/api/profile", response_model=CandidateProfile, tags=["Profile"])
def get_candidate_profile(current_user: CurrentUser):
    """Fetches candidate profile from user's isolated profile.json."""
    from app.core.user_storage import load_user_profile
    return load_user_profile(user_id=current_user.id)

@app.put("/api/profile", response_model=CandidateProfile, tags=["Profile"])
def update_candidate_profile(profile_data: CandidateProfile, current_user: CurrentUser):
    """Updates candidate profile in user's isolated profile.json dynamically (Rule 5: Zero Stale Data)."""
    from app.core.user_storage import save_user_profile
    from app.agent.scheduler import autopilot_scheduler
    user_id = current_user.id
    save_user_profile(user_id=user_id, profile=profile_data)
    try:
        autopilot_scheduler.nudge()
    except Exception:
        pass
    return profile_data

@app.post("/api/profile/upload-resume", tags=["Profile"])
async def upload_candidate_resume(current_user: CurrentUser, file: UploadFile = File(...)):
    """
    Uploads a PDF resume, parses skills & projects using AI,
    and automatically updates the candidate master profile in their isolated vault.
    """
    from app.core.user_storage import get_user_resume_path, load_user_profile
    user_id = current_user.id

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files (.pdf) are supported for resume parsing.")

    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if not contents.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="File is not a valid PDF (missing %PDF magic header).")

    # 1. Save uploaded PDF to user's isolated vault
    save_path = get_user_resume_path(user_id)
    with open(save_path, "wb") as f:
        f.write(contents)

    # 2. Extract text from PDF
    text = ""
    try:
        from app.agent.resume_parser import extract_text_from_pdf, parse_resume_content
        text = extract_text_from_pdf(contents)
    except Exception as e:
        logger.warning(f"Text extraction warning: {e}")

    # 3. AI extraction & merge into user's profile.json
    try:
        from app.agent.resume_parser import parse_resume_content
        updated_profile = parse_resume_content(resume_text=text, pdf_bytes=contents, user_id=user_id)
        return {
            "status": "success",
            "message": f"Resume '{file.filename}' parsed and saved to Master Profile!",
            "filename": file.filename,
            "profile": updated_profile
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Resume Parsing error: {str(e)}")

@app.get("/api/profile/download-uploaded-resume", tags=["Profile"])
def download_uploaded_resume(
    request: Request,
    current_user: CurrentUserOrQuery,
    inline: bool = False,
    token: Optional[str] = Query(None, description="Optional JWT token for direct browser downloads"),
    db: DbSession = None,
):
    """Downloads candidate's original uploaded master resume from their isolated vault."""
    from app.core.user_storage import get_user_resume_path, load_user_profile
    user = current_user
    if user is None:
        user = get_current_user_from_token_or_header(request=request, token=token, db=db)
    user_id = user.id
    resume_path = get_user_resume_path(user_id)
    if not resume_path.exists():
        raise HTTPException(status_code=404, detail="No uploaded resume found for this candidate.")

    profile = load_user_profile(user_id)
    candidate_name = getattr(profile.personal_info, "name", "Candidate") or "Candidate"
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", candidate_name)
    download_filename = f"{safe_name}_Master_Resume.pdf"

    return FileResponse(
        path=str(resume_path),
        filename=download_filename if not inline else None,
        media_type="application/pdf",
        content_disposition_type="inline" if inline else "attachment"
    )

@app.get("/api/profile/download-resume-pdf", tags=["Profile"])
def download_candidate_resume_pdf(
    request: Request,
    current_user: CurrentUserOrQuery,
    inline: bool = False,
    token: Optional[str] = Query(None, description="Optional JWT token for direct browser downloads"),
    db: DbSession = None,
):
    """Generates or downloads candidate resume in ATS PDF format scoped strictly to current_user."""
    from app.core.user_storage import get_user_resume_path, load_user_profile
    user = current_user
    if user is None:
        user = get_current_user_from_token_or_header(request=request, token=token, db=db)
    user_id = user.id
    resume_path = get_user_resume_path(user_id)

    profile = load_user_profile(user_id)
    candidate_name = getattr(profile.personal_info, "name", "Candidate") or "Candidate"
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", candidate_name)
    download_filename = f"{safe_name}_Resume.pdf"

    if resume_path.exists():
        return FileResponse(
            path=str(resume_path),
            filename=download_filename if not inline else None,
            media_type="application/pdf",
            content_disposition_type="inline" if inline else "attachment"
        )

    try:
        from app.agent.pdf_generator import generate_candidate_master_pdf
        pdf_path = generate_candidate_master_pdf(profile.model_dump(), output_filename=download_filename, user_id=user_id)
        return FileResponse(
            path=pdf_path,
            filename=download_filename if not inline else None,
            media_type="application/pdf",
            content_disposition_type="inline" if inline else "attachment"
        )
    except Exception as e:
        logger.error(f"Failed to generate resume PDF: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate resume PDF: {str(e)}")

@app.get("/api/jobs/{job_id}/tailored-resume-pdf", tags=["Applications"])
def download_tailored_resume_pdf(
    job_id: int,
    request: Request,
    db: DbSession,
    current_user: CurrentUserOrQuery,
    inline: bool = False,
    token: Optional[str] = Query(None, description="Optional JWT token for direct browser downloads"),
):
    """
    Downloads or previews the ATS-tailored PDF resume for a specific job scoped to current_user.
    Supports inline=True for iframe preview and inline=False for download.
    """
    user = current_user
    if user is None:
        user = get_current_user_from_token_or_header(request=request, token=token, db=db)
    user_id = user.id
    job = crud.get_job(db=db, job_id=job_id, user_id=user_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    app_rec = job.applications[0] if job.applications else None
    pdf_path = app_rec.tailored_resume_pdf_path if app_rec else None

    # If PDF already compiled and exists
    if pdf_path and Path(pdf_path).exists():
        safe_title = re.sub(r'[^a-zA-Z0-9_-]', '_', job.job_title)
        return FileResponse(
            path=pdf_path,
            filename=f"{safe_title}_Tailored_Resume.pdf" if not inline else None,
            media_type="application/pdf",
            content_disposition_type="inline" if inline else "attachment"
        )

    # Use uploaded master resume directly scoped to user_id
    from app.core.user_storage import get_user_resume
    uploaded_pdf = get_user_resume(user_id) if user_id else None
    if uploaded_pdf and uploaded_pdf.exists():
        candidate_info = _load_candidate_info(user_id=user_id)
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", candidate_info.name)
        return FileResponse(
            path=str(uploaded_pdf),
            filename=f"{safe_name}_Resume.pdf" if not inline else None,
            media_type="application/pdf",
            content_disposition_type="inline" if inline else "attachment"
        )

    raise HTTPException(
        status_code=404,
        detail="Master resume PDF not found. Please upload your resume in the Profile tab."
    )

# =====================================================================
# Phase 4: Assisted & Autonomous Application Workflow Endpoints
# =====================================================================

@app.post("/api/workflow/apply", response_model=WorkflowStatusResponse, tags=["Workflow"])
async def trigger_apply_workflow(req: ApplyWorkflowRequest, db: DbSession, current_user: CurrentUser):
    """
    Sub-Phase 4.4: Triggers the LangGraph Assisted/Autonomous Application State Machine scoped to current_user.
    - Evaluates job match (if not already evaluated).
    - Auto-tailors ATS resume (if not already tailored).
    - Stages form fields & captures Playwright visual snapshot.
    - If assisted mode: Safely pauses at Human Review Gateway via native interrupt.
    - If autonomous mode: Submits directly.
    NOTE: Runs in a background thread via asyncio.to_thread to prevent blocking the
    FastAPI event loop during long-running Playwright + Gemini operations.
    """
    user_id = current_user.id
    job = crud.get_job(db=db, job_id=req.job_id, user_id=user_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    ev = job.evaluation
    app_rec = job.applications[0] if job.applications else None

    # Use existing tailored artifacts if available to maximize speed & avoid re-running AI
    tex_path = app_rec.tailored_resume_tex_path if app_rec else None
    pdf_path = app_rec.tailored_resume_pdf_path if app_rec else None
    cold_subj = app_rec.cold_email_subject if app_rec else None
    cold_body = app_rec.cold_email_body if app_rec else None
    linkedin_note = app_rec.linkedin_note if app_rec else None

    match_score = ev.match_score if ev else None

    # No mock/fallback target: a job without a real URL is reported as NO_URL by the workflow
    job_target_url = job.job_url or ""

    # Capture local vars for thread (db session must NOT be passed into thread)
    _job_title = job.job_title
    _company_name = job.company_name
    _job_description = job.job_description
    _job_id = job.id
    _location = job.location or "Remote"
    _portal_name = req.portal_name
    _mode = req.mode

    try:
        # Run the blocking LangGraph + Playwright workflow in a worker thread
        # to avoid freezing the FastAPI async event loop (which causes timeout "cancellations")
        wf_res = await asyncio.to_thread(
            run_application_workflow,
            job_title=_job_title,
            company_name=_company_name,
            job_description=_job_description,
            job_url=job_target_url,
            portal_name=_portal_name,
            location=_location,
            job_id=_job_id,
            match_score=match_score,
            requires_human_approval=(_mode == "assisted"),
            tailored_resume_tex_path=tex_path,
            tailored_resume_pdf_path=pdf_path,
            cold_email_subject=cold_subj,
            cold_email_body=cold_body,
            linkedin_connection_note=linkedin_note,
            is_manual_override=True,
            user_id=current_user.id,
        )

        state = wf_res["state"]
        is_interrupted = wf_res["is_interrupted"]
        payload = wf_res["interrupt_payload"]

        # Formulate web-accessible URL for review snapshot
        review_url = None
        snap_path = payload.get("review_snapshot_path") if payload else state.get("review_snapshot_path")
        if snap_path:
            p = Path(snap_path)
            review_url = f"/output/snapshots/{p.name}"

        conf_url = None
        conf_path = state.get("confirmation_snapshot_path")
        if conf_path:
            p = Path(conf_path)
            conf_url = f"/output/snapshots/{p.name}"

        return WorkflowStatusResponse(
            thread_id=wf_res["thread_id"],
            status=state.get("status", "REVIEW_GATEWAY" if is_interrupted else "SUBMITTED"),
            is_interrupted=is_interrupted,
            interrupt_payload=payload,
            review_snapshot_url=review_url,
            confirmation_snapshot_url=conf_url,
            execution_logs=state.get("execution_logs", [])
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Workflow execution error: {str(e)}")

@app.post("/api/workflow/{thread_id}/resume", response_model=WorkflowStatusResponse, tags=["Workflow"])
async def resume_apply_workflow(thread_id: str, req: ResumeWorkflowRequest, current_user: CurrentUser):
    """
    Sub-Phase 4.4: Resumes an interrupted workflow upon candidate decision (Approve or Reject) scoped strictly to current_user.
    When approved: Playwright executes final submission click and captures confirmation snapshot.
    NOTE: Runs in a background thread via asyncio.to_thread to prevent blocking the event loop.
    """
    # Multi-Tenant Session Ownership Guard (In-memory + Persisted Storage)
    from app.core.user_storage import get_workflow_session
    pending_session = WORKFLOW_SESSIONS.get(thread_id) or get_workflow_session(thread_id, user_id=current_user.id)
    if not pending_session:
        other_user_session = get_workflow_session(thread_id)
        if other_user_session and other_user_session.get("user_id") != current_user.id:
            logger.warning(
                f"🚨 Anti-Hijack: User {current_user.id} attempted to resume workflow {thread_id} "
                f"belonging to User {other_user_session.get('user_id')}!"
            )
            raise HTTPException(status_code=403, detail="Access denied: Cannot resume or reject another user's application workflow.")
        raise HTTPException(status_code=404, detail="Workflow session not found or has already been decided.")
    elif pending_session.get("user_id") != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied: Cannot resume or reject another user's application workflow.")

    try:
        res = await asyncio.to_thread(
            resume_application_workflow,
            thread_id=thread_id,
            approved=req.approved,
            reason=req.reason,
            user_id=current_user.id,
        )

        state = res["state"]
        conf_url = None
        conf_path = state.get("confirmation_snapshot_path")
        if conf_path:
            conf_url = f"/output/snapshots/{Path(conf_path).name}"

        review_url = None
        snap_path = state.get("review_snapshot_path")
        if snap_path:
            review_url = f"/output/snapshots/{Path(snap_path).name}"

        return WorkflowStatusResponse(
            thread_id=thread_id,
            status=res["status"],
            is_interrupted=res["is_interrupted"],
            interrupt_payload=None,
            review_snapshot_url=review_url,
            confirmation_snapshot_url=conf_url,
            execution_logs=res["execution_logs"]
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Workflow resume error: {str(e)}")

@app.get("/api/workflow/qa", response_model=List[QAItemResponse], tags=["Workflow"])
def get_screening_qa_bank(db: DbSession, current_user: CurrentUser):
    """Returns all verified screening questions and answers stored in the memory bank scoped to current_user."""
    user_id = current_user.id
    qa_bank.seed_default_qa_bank(user_id=user_id)
    records = crud.list_qa_answers(db, user_id=user_id)
    return [
        QAItemResponse(id=r.id, question=r.question, answer=r.answer, category=r.category)
        for r in records
    ]

@app.post("/api/workflow/qa", response_model=QAItemResponse, tags=["Workflow"])
def save_screening_qa_item(req: SaveQARequest, db: DbSession, current_user: CurrentUser):
    """Saves or updates a screening question in the candidate's memory bank scoped to current_user."""
    user_id = current_user.id
    qa = crud.save_qa_answer(db, question=req.question, answer=req.answer, category=req.category, user_id=user_id)
    return QAItemResponse(id=qa.id, question=qa.question, answer=qa.answer, category=qa.category)


# =====================================================================
# Sub-Phase 5.4: Account Connection Settings & Recruiter Outreach
# =====================================================================

@app.get("/api/settings", tags=["Settings"])
def get_user_settings(current_user: CurrentUser):
    """Returns portal accounts and SMTP outreach configuration with masked passwords scoped strictly to current_user."""
    return get_masked_settings(user_id=current_user.id)

@app.put("/api/settings", tags=["Settings"])
def update_user_settings(req: UpdateAccountSettingsRequest, current_user: CurrentUser):
    """Updates candidate portal credentials and Gmail SMTP outreach configuration scoped strictly to current_user."""
    settings = load_account_settings(user_id=current_user.id)

    if req.smtp_sender_email is not None:
        settings.smtp.sender_email = req.smtp_sender_email.strip()
    if req.smtp_sender_name is not None:
        settings.smtp.sender_name = req.smtp_sender_name.strip()
    if req.smtp_app_password is not None and req.smtp_app_password != "••••••••••••••••":
        settings.smtp.app_password = req.smtp_app_password.replace(" ", "")
    if req.smtp_daily_limit is not None:
        settings.smtp.daily_limit = req.smtp_daily_limit
    if req.smtp_enabled is not None:
        settings.smtp.enabled = req.smtp_enabled

    # Support nested smtp dictionary if provided by frontend
    if req.smtp:
        if req.smtp.sender_email is not None:
            settings.smtp.sender_email = req.smtp.sender_email.strip()
        if req.smtp.sender_name is not None:
            settings.smtp.sender_name = req.smtp.sender_name.strip()
        if req.smtp.app_password is not None and req.smtp.app_password != "••••••••••••••••":
            settings.smtp.app_password = req.smtp.app_password.replace(" ", "")
        if req.smtp.daily_limit is not None:
            settings.smtp.daily_limit = req.smtp.daily_limit
        if req.smtp.enabled is not None:
            settings.smtp.enabled = req.smtp.enabled

    if req.portals:
        for p_name, p_input in req.portals.items():
            if p_name not in settings.portals:
                settings.portals[p_name] = PortalAccountConfig()
            curr = settings.portals[p_name]
            if p_input.username is not None:
                curr.username = p_input.username.strip()
            # Portal passwords are never stored: the portal login is the persistent browser session.
            # Any previously stored password is cleared here.
            curr.password = ""
            curr.status = "connected" if curr.username else "unconfigured"

    save_account_settings(settings, user_id=current_user.id)
    return {"status": "success", "message": "Settings updated successfully", "settings": get_masked_settings(user_id=current_user.id)}


# =====================================================================
# Auto-Pilot Scheduling & Task Queue Endpoints (Multi-Tenant Scoped)
# =====================================================================
from app.agent.scheduler import autopilot_scheduler
from app.agent.task_queue import task_queue

@app.get("/api/autopilot/status", tags=["Auto-Pilot"])
def get_autopilot_status(current_user: CurrentUser):
    """Returns current auto-pilot execution state and next schedule, scoped strictly to current_user."""
    return autopilot_scheduler.get_status(user_id=current_user.id)


@app.post("/api/autopilot/run-now", tags=["Auto-Pilot"])
async def trigger_autopilot_now(current_user: CurrentUser):
    """Triggers an immediate discovery + apply run outside the regular schedule, scoped strictly to current_user."""
    user_id = current_user.id
    logger.info(f"Manual auto-pilot trigger requested for User {user_id}")
    task_id = await autopilot_scheduler.trigger_user_now(user_id=user_id)
    return {
        "status": "triggered",
        "user_id": user_id,
        "task_id": task_id,
        "message": f"Auto-Pilot manual cycle initiated in background queue for User {user_id}."
    }


@app.post("/api/autopilot/toggle", tags=["Auto-Pilot"])
async def toggle_autopilot(current_user: CurrentUser):
    """Toggles Auto-Pilot on/off for current_user in private profile vault and intelligently coordinates with office timetable."""
    import asyncio
    from app.core.user_storage import load_user_profile, save_user_profile
    from app.agent.scheduler import get_now_ist, get_portal_timeline_slot
    user_id = current_user.id
    profile = load_user_profile(user_id)
    new_state = not getattr(profile.preferences, "autopilot_enabled", False)
    profile.preferences.autopilot_enabled = new_state
    save_user_profile(user_id, profile)

    # Intelligent timetable coordination:
    # 1. If turned ON during active work hours & in "work" phase -> trigger immediately!
    # 2. If turned ON during "break" or "closed" hours -> respect rest/night cadence; scheduler activates when next slot arrives.
    if new_state:
        slot_info = get_portal_timeline_slot(get_now_ist(), user_id=user_id)
        if slot_info.get("is_office_hours") and slot_info.get("phase") == "work":
            asyncio.create_task(autopilot_scheduler.trigger_user_now(user_id=user_id))
        else:
            autopilot_scheduler.nudge()
    else:
        autopilot_scheduler.nudge()

    return {
        "user_id": user_id,
        "autopilot_enabled": new_state,
        "message": f"Auto-Pilot {'enabled' if new_state else 'disabled'} for User {user_id}."
    }


@app.get("/api/autopilot/tasks", tags=["Auto-Pilot"])
def get_user_tasks(current_user: CurrentUser):
    """Returns background tasks strictly belonging to current_user."""
    return task_queue.list_user_tasks(current_user.id)


@app.post("/api/autopilot/tasks/{task_id}/cancel", tags=["Auto-Pilot"])
async def cancel_user_task(task_id: str, current_user: CurrentUser):
    """Cancels a pending task strictly verifying tenant ownership."""
    from fastapi import HTTPException
    user_id = current_user.id
    task = task_queue.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied: Cannot cancel tasks belonging to another user.")
    success = await task_queue.cancel_task(task_id, user_id=user_id)
    return {"task_id": task_id, "status": "cancelled" if success else "failed"}


@app.post("/api/autopilot/boost-profile", tags=["Auto-Pilot"])
async def trigger_profile_boost(current_user: CurrentUser):
    """Triggers an on-demand profile booster for current_user's Naukri account."""
    user_id = current_user.id
    logger.info(f"Manual profile boost requested for User {user_id}")
    from app.agent.booster import boost_naukri_profile_live
    res = await boost_naukri_profile_live(user_id=user_id)
    return res


# =====================================================================
# Portal Session Endpoints (Naukri Persistent Session Scoped per User)
# =====================================================================
@app.get("/api/portals/naukri/session-status", tags=["Portals"])
def get_naukri_session_status(current_user: CurrentUser):
    """Checks if a valid persistent browser session exists for Naukri scoped to current_user."""
    import json
    from datetime import datetime, timezone
    from app.core.user_storage import get_user_browser_session_dir
    user_id = current_user.id
    session_dir = get_user_browser_session_dir(user_id)
    marker_file = session_dir / "session_verified.json"
    
    is_connected = marker_file.exists()
    verified_data = {}
    is_expired = False
    age_days = 0.0
    
    if is_connected:
        try:
            verified_data = json.loads(marker_file.read_text(encoding="utf-8"))
            verified_at_str = verified_data.get("verified_at")
            if verified_at_str:
                clean_dt_str = verified_at_str.replace("Z", "+00:00")
                verified_dt = datetime.fromisoformat(clean_dt_str)
                age_days = round((datetime.now(timezone.utc) - verified_dt).total_seconds() / 86400, 1)
                # Naukri sessions expire after 25 days
                if age_days > 25:
                    is_expired = True
                    is_connected = False
        except Exception as e:
            logger.debug(f"Error parsing verified_at: {e}")
            
    status_label = "connected" if is_connected else ("expired" if is_expired else "unconfigured")
    if is_connected:
        message = f"Naukri persistent session active (Connected {age_days}d ago • OTP verified)"
    elif is_expired:
        message = f"Naukri session expired ({age_days} days old). Please click Re-login to refresh cookies."
    else:
        message = "No active Naukri session found. Please launch session login."

    return {
        "portal": "naukri",
        "connected": is_connected,
        "expired": is_expired,
        "age_days": age_days,
        "status": status_label,
        "session_dir": str(session_dir),
        "verified_at": verified_data.get("verified_at"),
        "cookie_count": verified_data.get("cookie_count", 0),
        "message": message,
        "user_id": user_id,
    }


@app.post("/api/portals/naukri/disconnect", tags=["Portals"])
def disconnect_naukri_session(current_user: CurrentUser):
    """Safely disconnects Naukri persistent session scoped strictly to current_user."""
    from app.core.user_storage import get_user_browser_session_dir
    user_id = current_user.id
    session_dir = get_user_browser_session_dir(user_id)
    marker_file = session_dir / "session_verified.json"
    if marker_file.exists():
        marker_file.unlink()
    return {
        "status": "disconnected",
        "portal": "naukri",
        "user_id": user_id,
        "message": "Naukri session disconnected successfully."
    }


@app.post("/api/portals/naukri/launch-session", tags=["Portals"])
async def launch_naukri_session(current_user: CurrentUser):
    """Deprecated legacy desktop launcher. Safely guides clients to the cloud-native Mobile OTP gateway."""
    logger.info(f"Desktop launch-session invoked by User {current_user.id}; safely returning deprecation notice.")
    return {
        "status": "deprecated",
        "portal": "naukri",
        "user_id": current_user.id,
        "message": "Desktop CMD session launch is deprecated in multi-user cloud mode. Please connect via Mobile OTP (/api/portals/naukri/connect-mobile)."
    }


@app.post("/api/portals/naukri/connect-mobile", response_model=NaukriConnectResponse, tags=["Portals"])
async def connect_naukri_mobile(req: NaukriMobileConnectRequest, current_user: CurrentUser):
    """
    Dual-Mode Mobile Portal Connection.
    Initiates a silent background login session for Naukri in a worker thread scoped strictly to current_user.
    Returns status:
      - 'OTP_REQUIRED': with session_id to prompt mobile user for SMS OTP.
      - 'SUCCESS': if user was already logged in or completed directly.
      - 'ERROR': if credentials or connection failed.
    """
    logger.info(f"Mobile Naukri connection requested for User {current_user.id} (identifier: {req.identifier[:4]}***)")
    result = await headless_auth_manager.start_naukri_login(
        identifier=req.identifier,
        password=req.password,
        use_otp_mode=bool(req.use_otp),
        user_id=current_user.id,
    )
    return NaukriConnectResponse(**result)


@app.post("/api/portals/naukri/verify-otp", response_model=NaukriConnectResponse, tags=["Portals"])
async def verify_naukri_mobile_otp(req: NaukriVerifyOtpRequest, current_user: CurrentUser):
    """
    Dual-Mode Mobile Portal Connection.
    Submits user's 6-digit SMS OTP to the active headless browser session verifying session ownership.
    Saves authenticated cookies to permanent storage and completes connection.
    """
    logger.info(f"Mobile Naukri OTP verification received for User {current_user.id} (session: {req.session_id})")
    pending = headless_auth_manager._active_sessions.get(req.session_id)
    if pending and pending.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied: Cannot verify OTP for another user's session.")
    result = await headless_auth_manager.verify_naukri_otp(
        session_id=req.session_id,
        otp=req.otp,
        expected_user_id=current_user.id,
    )
    return NaukriConnectResponse(**result)


@app.post("/api/portals/naukri/cancel-mobile", tags=["Portals"])
async def cancel_naukri_mobile_session(req: NaukriCancelSessionRequest, current_user: CurrentUser):
    """Cancels a pending headless login session verifying session ownership."""
    pending = headless_auth_manager._active_sessions.get(req.session_id)
    if pending and pending.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied: Cannot cancel another user's session.")
    await headless_auth_manager.close_session(req.session_id)
    return {"status": "cancelled", "message": "Login session cancelled successfully."}



@app.get("/api/portals/indeed/session-status", tags=["Portals"])
def get_indeed_session_status(current_user: CurrentUser):
    """Checks if a valid persistent browser session exists for Indeed scoped strictly to current_user."""
    import json
    from datetime import datetime, timezone
    from app.core.user_storage import get_user_indeed_session_dir
    session_dir = get_user_indeed_session_dir(current_user.id)
    marker_file = session_dir / "session_verified.json"
    
    is_connected = marker_file.exists()
    verified_data = {}
    is_expired = False
    age_days = 0.0
    
    if is_connected:
        try:
            verified_data = json.loads(marker_file.read_text(encoding="utf-8"))
            verified_at_str = verified_data.get("verified_at")
            if verified_at_str:
                clean_dt_str = verified_at_str.replace("Z", "+00:00")
                verified_dt = datetime.fromisoformat(clean_dt_str)
                age_days = round((datetime.now(timezone.utc) - verified_dt).total_seconds() / 86400, 1)
                # Indeed sessions expire after 30 days
                if age_days > 30:
                    is_expired = True
                    is_connected = False
        except Exception as e:
            logger.debug(f"Error parsing indeed verified_at: {e}")
            
    status_label = "connected" if is_connected else ("expired" if is_expired else "unconfigured")
    if is_connected:
        message = f"Indeed persistent session active (Connected {age_days}d ago • Logged in)"
    elif is_expired:
        message = f"Indeed session expired ({age_days} days old). Please click Re-login to refresh cookies."
    else:
        message = "No active Indeed session found. Please launch session login."

    return {
        "portal": "indeed",
        "connected": is_connected,
        "expired": is_expired,
        "age_days": age_days,
        "status": status_label,
        "session_dir": str(session_dir),
        "verified_at": verified_data.get("verified_at"),
        "cookie_count": verified_data.get("cookie_count", 0),
        "message": message
    }


@app.post("/api/portals/indeed/launch-session", tags=["Portals"])
async def launch_indeed_session(current_user: CurrentUser):
    """Deprecated legacy desktop launcher. Safely guides clients to the cloud-native Mobile OTP gateway."""
    logger.info(f"Desktop Indeed launch-session invoked by User {current_user.id}; safely returning deprecation notice.")
    return {
        "status": "deprecated",
        "portal": "indeed",
        "user_id": current_user.id,
        "message": "Desktop CMD session launch is deprecated in multi-user cloud mode. Please connect via Mobile OTP (/api/portals/indeed/connect-mobile)."
    }


@app.post("/api/portals/indeed/connect-mobile", response_model=IndeedConnectResponse, tags=["Portals"])
async def connect_indeed_mobile(req: IndeedMobileConnectRequest, current_user: CurrentUser):
    """
    Dual-Mode Mobile Portal Connection for Indeed.
    Initiates a silent background login session for Indeed in a worker thread scoped strictly to current_user.
    Returns status:
      - 'OTP_REQUIRED': with session_id to prompt mobile user for verification code / OTP.
      - 'SUCCESS': if user was already logged in or completed directly.
      - 'ERROR': if credentials or connection failed.
    """
    logger.info(f"Mobile Indeed connection requested for User {current_user.id} (identifier: {req.identifier[:4]}***)")
    result = await headless_auth_manager.start_indeed_login(
        identifier=req.identifier,
        password=req.password,
        use_code_mode=bool(req.use_code),
        user_id=current_user.id,
    )
    return IndeedConnectResponse(**result)


@app.post("/api/portals/indeed/verify-otp", response_model=IndeedConnectResponse, tags=["Portals"])
async def verify_indeed_mobile_otp(req: IndeedVerifyOtpRequest, current_user: CurrentUser):
    """
    Dual-Mode Mobile Portal Connection for Indeed.
    Submits user's verification code / OTP to the active headless browser session verifying session ownership.
    Saves authenticated cookies to permanent storage and completes connection.
    """
    logger.info(f"Mobile Indeed OTP/code verification received for User {current_user.id} (session: {req.session_id})")
    pending = headless_auth_manager._active_sessions.get(req.session_id)
    if pending and pending.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied: Cannot verify OTP for another user's session.")
    result = await headless_auth_manager.verify_indeed_otp(
        session_id=req.session_id,
        otp=req.verification_code,
        expected_user_id=current_user.id,
    )
    return IndeedConnectResponse(**result)


@app.post("/api/portals/indeed/cancel-mobile", tags=["Portals"])
async def cancel_indeed_mobile_session(req: IndeedCancelSessionRequest, current_user: CurrentUser):
    """Cancels a pending headless Indeed login session verifying session ownership."""
    pending = headless_auth_manager._active_sessions.get(req.session_id)
    if pending and pending.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied: Cannot cancel another user's session.")
    await headless_auth_manager.close_session(req.session_id)
    return {"status": "cancelled", "message": "Indeed login session cancelled successfully."}








