"""
Module: main.py
Purpose: Step 2.2 FastAPI Backend Server - Central API connecting AI Brain, Database, and Dashboard.
Standards: Rule 1 (Zero Blind Trust), Rule 2 (Strict Pydantic Validation & Locked CORS),
           Rule 3 (Low Code & High Accuracy), Rule 4 (Standard Layout), Rule 5 (Production Reliability).
"""
import json
import asyncio
import logging
import os
import re
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

from app.config import CORS_ORIGINS, OUTPUT_DIR, BASE_DIR
from app.db.session import init_db, get_db

DbSession = Annotated[Session, Depends(get_db)]

from app.db import crud
from app.agent import scorer, outreach, discover_and_ingest, IngestionReport, qa_bank
from app.agent.workflow import run_application_workflow, resume_application_workflow
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
    DetailedAnalyticsResponse,
    TestSMTPRequest,
    SendColdEmailRequest,
    UpdateAccountSettingsRequest,
)
from app.agent.mailer import (
    load_account_settings,
    save_account_settings,
    get_masked_settings,
    test_smtp_connection,
    send_cold_email,
    PortalAccountConfig,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes SQLite database tables and registers main event loop with EventBus."""
    init_db()
    try:
        loop = asyncio.get_running_loop()
        event_bus.set_event_loop(loop)
    except Exception:
        pass
    yield

app = FastAPI(
    title="Autonomous Job Automation Agent API",
    description="Production REST API powering autonomous job discovery, ATS scoring, resume tailoring, and tracking.",
    version="1.0.0",
    lifespan=lifespan
)

# -------------------------------------------------------------------
# Optional API Token Middleware (Security Fix)
# Set API_TOKEN in backend/.env to enable token-based auth.
# If API_TOKEN is NOT set, the server remains open for local use.
# Clients must send: X-API-Token: <your-token>
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
            client_token = request.headers.get("X-API-Token", "")
            if client_token != _API_TOKEN:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Unauthorized: Invalid or missing X-API-Token header."}
                )
    return await call_next(request)

# Rule 2: Strict CORS Protection with local network & loopback support
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve generated resume files (PDF/TeX) statically for browser download
app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")

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
async def stream_events(request: Request, topic: str = Query("all")):
    """
    Sub-Phase 5.1: Real-Time Server-Sent Events (SSE) Stream.
    Clients subscribe to real-time workflow, discovery, or system progress events.
    Supports topic filtering (e.g. topic=workflow:1, topic=discovery, or topic=all).
    Includes automatic 15-second heartbeat ping to prevent timeouts.
    """
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
def analyze_job(req: AnalyzeJobRequest, db: DbSession):
    """
    Unified Autonomous Pipeline Endpoint:
    1. AI Scorer evaluates match score and skills.
    2. Saves Job and Evaluation to SQLite.
    3. If score >= 60%, automatically tailors resume and generates cold outreach.
    4. Saves Application tracking record to SQLite.
    """
    # 1. AI ATS Scoring (Phase 1 AI Brain)
    match_result = scorer.analyze_and_score_job(req.job_description)

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
        salary_range=req.salary_range or ""
    )

    # 3. Persist Evaluation to SQLite
    crud.save_job_evaluation(db=db, job_id=job.id, match=match_result)

    tex_path = ""
    pdf_path = None
    cold_subject = ""
    cold_body = ""
    linkedin_note = ""
    app_status = "Saved"

    # 4. Auto-tailor ATS resume and generate cold outreach for viable roles (score >= 60%)
    if match_result.match_score >= 60:
        from app.agent.tailorer import tailor_resume
        tailor_out = tailor_resume(req.job_description, match_result)
        tex_path = tailor_out.get("tex_path", "")
        master_pdf = BASE_DIR / "data" / "uploaded_resume.pdf"
        pdf_path = tailor_out.get("pdf_path") or (str(master_pdf) if master_pdf.exists() else None)

        outreach_pkg = outreach.generate_outreach(
            job_description=req.job_description,
            match_result=match_result,
            recipient_role=req.recipient_role
        )
        cold_subject = outreach_pkg.subject_line
        cold_body = outreach_pkg.cold_email_body
        linkedin_note = outreach_pkg.linkedin_connection_note
        app_status = "Tailored"

    # 5. Persist Application Pipeline Tracking Record
    crud.create_or_update_application(
        db=db,
        job_id=job.id,
        status=app_status,
        tex_path=tex_path,
        pdf_path=pdf_path or "",
        cold_subject=cold_subject,
        cold_body=cold_body,
        linkedin_note=linkedin_note
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
async def trigger_job_discovery(req: DiscoverJobsRequest):
    """
    Unified Multi-Portal Discovery & Autonomous Ingestion Endpoint (Phase 3):
    1. Scrapes fresh postings across requested portals (LinkedIn, Indeed, Naukri, Glassdoor).
    2. Smart deduplication filters out already-tracked jobs in SQLite.
    3. Gemini evaluates ATS match score.
    4. Auto-triages high matches (>= 75%) to 'Ready' + Tailors LaTeX Resume + Generates Outreach.
    5. Auto-triages low matches (< 75%) to 'Archived'.
    6. Returns structured IngestionReport.
    """
    try:
        report = await discover_and_ingest(
            search_term=req.search_term,
            location=req.location,
            portals=req.portals,
            results_wanted=req.results_wanted,
            min_match_score=req.min_match_score,
            max_jobs_to_process=req.max_process,
        )
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Discovery engine error: {str(e)}")

@app.get("/api/jobs", response_model=List[JobListItem], tags=["Pipeline"])
def list_all_jobs(
    db: DbSession,
    status_filter: Optional[str] = Query(None, alias="status"),
    skip: int = 0,
    limit: int = 100,
):
    """Retrieves all tracked jobs from SQLite with evaluations and pipeline status."""
    jobs = crud.list_jobs(db=db, skip=skip, limit=limit, status=status_filter)
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
            created_at=j.created_at.isoformat()
        ))
    return results

@app.get("/api/jobs/{job_id}", response_model=JobDetailResponse, tags=["Pipeline"])
def get_job_detail(job_id: int, db: DbSession):
    """Retrieves complete details for a single job including evaluation and application state."""
    job = crud.get_job(db=db, job_id=job_id)
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

    # Resolve master PDF resume path fallback
    master_pdf = Path(__file__).resolve().parent / "data" / "uploaded_resume.pdf"
    pdf_path = (app_rec.tailored_resume_pdf_path if app_rec and app_rec.tailored_resume_pdf_path else "")
    if not pdf_path and master_pdf.exists():
        pdf_path = str(master_pdf)

    # Dynamic fallback for candidate name & cold email subject/body
    candidate_name = "Rayavaram Jayasurya"
    try:
        from app.agent.scorer import load_profile
        candidate_name = load_profile().personal_info.name
    except Exception:
        pass

    cold_subj = (app_rec.cold_email_subject if app_rec and app_rec.cold_email_subject else f"Application: {job.job_title} - {candidate_name}")
    cold_body = (app_rec.cold_email_body if app_rec and app_rec.cold_email_body else (
        f"Dear Hiring Team,\n\n"
        f"I am writing to express my strong interest in the {job.job_title} position at {job.company_name}.\n\n"
        f"With proven hands-on experience in Python, building agentic AI workflows, and developing scalable architectures, "
        f"I am confident in delivering high impact immediately. I have a 0-day notice period and am available to join right away.\n\n"
        f"Please find my resume attached below for your review. I look forward to speaking with you.\n\n"
        f"Best regards,\n"
        f"{candidate_name}\n"
        f"Phone: +91 9381744883"
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
def get_job_resume(job_id: int, db: DbSession):
    """Fetches the generated resume content and download paths."""
    job = crud.get_job(db=db, job_id=job_id)
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
def update_job_status(job_id: int, req: UpdateStatusRequest, db: DbSession):
    """Updates application pipeline status (e.g. Saved -> Tailored -> Applied -> Interview)."""
    job = crud.get_job(db=db, job_id=job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    app_rec = crud.create_or_update_application(db=db, job_id=job.id, status=req.status, notes=req.notes or "")
    return {"status": "success", "job_id": job.id, "new_status": app_rec.status}

@app.delete("/api/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Pipeline"])
def delete_tracked_job(job_id: int, db: DbSession):
    """Deletes a job and cascades deletion to all associated evaluations and application data."""
    deleted = crud.delete_job(db=db, job_id=job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Job not found")
    return None

@app.get("/api/metrics", response_model=PipelineMetrics, tags=["Dashboard"])
def get_pipeline_metrics(db: DbSession):
    """Calculates live metrics for the dashboard cards."""
    jobs = crud.list_jobs(db=db, skip=0, limit=1000)
    total = len(jobs)
    scores = [j.evaluation.match_score for j in jobs if j.evaluation]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0

    applied_count = sum(1 for j in jobs if j.applications and j.applications[0].status == "Applied")
    interview_count = sum(1 for j in jobs if j.applications and j.applications[0].status == "Interview")
    offer_count = sum(1 for j in jobs if j.applications and j.applications[0].status == "Offer")
    ready_count = sum(1 for j in jobs if j.applications and j.applications[0].status == "Tailored")

    return PipelineMetrics(
        total_jobs=total,
        average_match_score=avg_score,
        ready_to_apply_count=ready_count,
        applied_count=applied_count,
        interview_count=interview_count,
        offer_count=offer_count
    )

@app.get("/api/analytics", response_model=DetailedAnalyticsResponse, tags=["Dashboard"])
def get_comprehensive_analytics(db: DbSession):
    """
    Sub-Phase 5.3: Detailed Pipeline Analytics & Application Funnel Metrics.
    Returns conversion funnel, portal distribution, application velocity, and skill gap radar.
    """
    return crud.get_detailed_analytics(db=db)

@app.get("/api/profile", response_model=CandidateProfile, tags=["Profile"])
def get_candidate_profile():
    """Fetches candidate profile from profile.json."""
    profile_file = BASE_DIR / "profile.json"
    if not profile_file.exists():
        raise HTTPException(status_code=404, detail="profile.json not found")
    with open(profile_file, "r", encoding="utf-8") as f:
        return CandidateProfile(**json.load(f))

@app.put("/api/profile", response_model=CandidateProfile, tags=["Profile"])
def update_candidate_profile(profile_data: CandidateProfile):
    """Updates candidate profile in profile.json dynamically (Rule 5: Zero Stale Data)."""
    profile_file = BASE_DIR / "profile.json"
    with open(profile_file, "w", encoding="utf-8") as f:
        json.dump(profile_data.model_dump(), f, indent=2)
    return profile_data

@app.post("/api/profile/upload-resume", tags=["Profile"])
async def upload_candidate_resume(file: UploadFile = File(...)):
    """
    Uploads a PDF resume, parses skills & projects using AI,
    and automatically updates the candidate master profile.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files (.pdf) are supported for resume parsing.")

    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # 1. Save uploaded PDF to data directory
    save_path = BASE_DIR / "data" / "uploaded_resume.pdf"
    with open(save_path, "wb") as f:
        f.write(contents)

    # 2. Extract text from PDF
    try:
        from app.agent.resume_parser import extract_text_from_pdf, parse_resume_content
        text = extract_text_from_pdf(contents)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read PDF document: {str(e)}")

    if not text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from PDF. Ensure the PDF contains readable text.")

    # 3. AI extraction & merge into profile.json
    try:
        updated_profile = parse_resume_content(text)
        return {
            "status": "success",
            "message": f"Resume '{file.filename}' parsed and saved to Master Profile!",
            "filename": file.filename,
            "profile": updated_profile
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Resume Parsing error: {str(e)}")

@app.get("/api/profile/download-resume-pdf", tags=["Profile"])
def download_candidate_resume_pdf(inline: bool = False):
    """
    Generates and returns the latest Candidate Master Resume in ATS-standard PDF format.
    Serves uploaded resume if present, or dynamically generates from profile.json.
    Supports inline=True for modal iframe preview and inline=False for download.
    """
    profile_file = BASE_DIR / "profile.json"
    candidate_name = "Rayavaram_Jayasurya"
    profile_dict = {}
    if profile_file.exists():
        try:
            with open(profile_file, "r", encoding="utf-8") as f:
                profile_dict = json.load(f)
            candidate_name = profile_dict.get("personal_info", {}).get("name", "Rayavaram_Jayasurya")
        except Exception:
            pass

    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", candidate_name)
    download_filename = f"{safe_name}_Resume.pdf"

    uploaded_pdf = BASE_DIR / "data" / "uploaded_resume.pdf"
    if uploaded_pdf.exists():
        return FileResponse(
            path=str(uploaded_pdf),
            filename=download_filename if not inline else None,
            media_type="application/pdf",
            content_disposition_type="inline" if inline else "attachment"
        )

    try:
        from app.agent.pdf_generator import generate_candidate_master_pdf
        pdf_path = generate_candidate_master_pdf(profile_dict, output_filename=download_filename)
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
def download_tailored_resume_pdf(job_id: int, db: DbSession, inline: bool = False):
    """
    Downloads or previews the ATS-tailored PDF resume for a specific job.
    Supports inline=True for iframe preview and inline=False for download.
    """
    job = crud.get_job(db=db, job_id=job_id)
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

    # Fallback to uploaded master resume if available
    uploaded_pdf = BASE_DIR / "data" / "uploaded_resume.pdf"
    if uploaded_pdf.exists():
        return FileResponse(
            path=str(uploaded_pdf),
            filename=f"Rayavaram_Jayasurya_Resume.pdf" if not inline else None,
            media_type="application/pdf",
            content_disposition_type="inline" if inline else "attachment"
        )

    # Otherwise auto-tailor now
    try:
        from app.agent.tailorer import tailor_resume
        from app.schemas.match import JobMatchResult
        ev = job.evaluation
        skills_matched = ev.matching_skills if ev else []
        rec: Literal["Apply", "Review", "Skip"] = "Apply"
        if ev and ev.recommendation in ["Apply", "Review", "Skip"]:
            rec = cast(Literal["Apply", "Review", "Skip"], ev.recommendation)

        match_res = JobMatchResult(
            job_title=job.job_title,
            company_name=job.company_name,
            match_score=int(ev.match_score) if ev else 85,
            recommendation=rec,
            matching_skills=skills_matched,
            missing_skills=[],
            key_strengths=[],
            summary_reasoning="Strong match based on candidate profile and job requirements."
        )
        res = tailor_resume(job.job_description, match_res)
        if res.get("pdf_path") and Path(res["pdf_path"]).exists():
            if app_rec:
                app_rec.tailored_resume_pdf_path = res["pdf_path"]
                app_rec.tailored_resume_tex_path = res.get("tex_path") or ""
                db.commit()
            safe_title = re.sub(r'[^a-zA-Z0-9_-]', '_', job.job_title)
            return FileResponse(
                path=res["pdf_path"],
                filename=f"{safe_title}_Tailored_Resume.pdf" if not inline else None,
                media_type="application/pdf",
                content_disposition_type="inline" if inline else "attachment"
            )
        raise HTTPException(status_code=500, detail="Failed to compile tailored PDF resume")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tailoring failed: {str(e)}")

# =====================================================================
# Phase 4: Assisted & Autonomous Application Workflow Endpoints
# =====================================================================

@app.post("/api/workflow/apply", response_model=WorkflowStatusResponse, tags=["Workflow"])
async def trigger_apply_workflow(req: ApplyWorkflowRequest, db: DbSession):
    """
    Sub-Phase 4.4: Triggers the LangGraph Assisted/Autonomous Application State Machine.
    - Evaluates job match (if not already evaluated).
    - Auto-tailors ATS resume (if not already tailored).
    - Stages form fields & captures Playwright visual snapshot.
    - If assisted mode: Safely pauses at Human Review Gateway via native interrupt.
    - If autonomous mode: Submits directly.
    NOTE: Runs in a background thread via asyncio.to_thread to prevent blocking the
    FastAPI event loop during long-running Playwright + Gemini operations.
    """
    job = crud.get_job(db=db, job_id=req.job_id)
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

    # If job has no live URL, check if mock test portal or use direct fallback
    job_target_url = job.job_url
    if not job_target_url:
        mock_file = BASE_DIR / "data" / "mock_easy_apply.html"
        if mock_file.exists():
            job_target_url = str(mock_file)

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
            job_url=job_target_url or "",
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
async def resume_apply_workflow(thread_id: str, req: ResumeWorkflowRequest):
    """
    Sub-Phase 4.4: Resumes an interrupted workflow upon candidate decision (Approve or Reject).
    When approved: Playwright executes final submission click and captures confirmation snapshot.
    NOTE: Runs in a background thread via asyncio.to_thread to prevent blocking the event loop.
    """
    try:
        res = await asyncio.to_thread(
            resume_application_workflow,
            thread_id=thread_id,
            approved=req.approved,
            reason=req.reason
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Workflow resume error: {str(e)}")

@app.get("/api/workflow/qa", response_model=List[QAItemResponse], tags=["Workflow"])
def get_screening_qa_bank(db: DbSession):
    """Returns all verified screening questions and answers stored in the memory bank."""
    qa_bank.seed_default_qa_bank()
    records = crud.list_qa_answers(db)
    return [
        QAItemResponse(id=r.id, question=r.question, answer=r.answer, category=r.category)
        for r in records
    ]

@app.post("/api/workflow/qa", response_model=QAItemResponse, tags=["Workflow"])
def save_screening_qa_item(req: SaveQARequest, db: DbSession):
    """Saves or updates a screening question in the candidate's memory bank."""
    qa = crud.save_qa_answer(db, question=req.question, answer=req.answer, category=req.category)
    return QAItemResponse(id=qa.id, question=qa.question, answer=qa.answer, category=qa.category)


# =====================================================================
# Sub-Phase 5.4: Account Connection Settings & Recruiter Outreach
# =====================================================================

@app.get("/api/settings", tags=["Settings"])
def get_user_settings():
    """Returns portal accounts and SMTP outreach configuration with masked passwords."""
    return get_masked_settings()

@app.put("/api/settings", tags=["Settings"])
def update_user_settings(req: UpdateAccountSettingsRequest):
    """Updates candidate portal credentials and Gmail SMTP outreach configuration."""
    settings = load_account_settings()

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
            if p_input.password is not None and p_input.password != "••••••••••••":
                curr.password = p_input.password
            curr.status = "connected" if (curr.username and curr.password) else "unconfigured"

    save_account_settings(settings)
    return {"status": "success", "message": "Settings updated successfully", "settings": get_masked_settings()}

@app.post("/api/outreach/test-smtp", tags=["Outreach"])
def test_outreach_smtp(req: TestSMTPRequest):
    """Validates Gmail SMTP credentials without sending an email."""
    success, message = test_smtp_connection(
        host=req.host,
        port=req.port,
        sender_email=req.sender_email,
        app_password=req.app_password
    )
    if not success:
        raise HTTPException(status_code=400, detail=message)
    return {"status": "success", "message": message}

@app.post("/api/outreach/send-email", tags=["Outreach"])
def deliver_cold_email(req: SendColdEmailRequest, db: DbSession):
    """Delivers personalized cold outreach email with attached tailored PDF resume."""
    success, result_msg = send_cold_email(
        recipient_email=req.recipient_email,
        subject=req.subject,
        body_text=req.body,
        resume_pdf_path=req.resume_pdf_path,
        recipient_name=req.recipient_name
    )

    if not success:
        raise HTTPException(status_code=400, detail=result_msg)

    # If linked to a job, log the outreach in application notes
    if req.job_id:
        try:
            job = crud.get_job(db=db, job_id=req.job_id)
            if job and job.applications:
                app_rec = job.applications[0]
                existing_notes = app_rec.notes or ""
                new_note = f"[Outreach Sent to {req.recipient_email} at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}]"
                app_rec.notes = f"{existing_notes}\n{new_note}".strip()
                db.commit()
        except Exception as log_err:
            logger.warning(f"Could not record email note for job {req.job_id}: {log_err}")

    settings = load_account_settings()
    return {
        "status": "sent",
        "recipient": req.recipient_email,
        "detail": result_msg,
        "daily_sent": settings.emails_sent_today,
        "daily_limit": settings.smtp.daily_limit,
        "resume_attached": bool(req.resume_pdf_path)
    }


