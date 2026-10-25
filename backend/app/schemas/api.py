"""
Module: api.py
Purpose: Pydantic request and response schemas for FastAPI endpoints.
Standards: Rule 2 (Input Validation & Type-Safety), Rule 3 (Concise & Accurate).
"""
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

class AnalyzeJobRequest(BaseModel):
    """Payload sent to analyze, score, tailor, and track a job."""
    job_description: str = Field(..., min_length=20, description="Raw job description text")
    job_title: Optional[str] = Field(default="", description="Job title if known")
    company_name: Optional[str] = Field(default="", description="Company name if known")
    location: Optional[str] = Field(default="", description="Job location")
    portal_name: Optional[str] = Field(default="Manual", description="Source portal (e.g. LinkedIn, Indeed)")
    job_url: Optional[str] = Field(default="", description="Direct URL to posting")
    salary_range: Optional[str] = Field(default="", description="Salary range if stated")
    recipient_role: Literal["Technical_Lead", "HR_Recruiter"] = Field(
        default="Technical_Lead", description="Target cold outreach persona"
    )

class AnalyzeJobResponse(BaseModel):
    """Unified response returning AI score, tailored resume paths, and cold outreach text."""
    job_id: int
    job_title: str
    company_name: str
    location: str
    portal_name: str
    job_url: str
    match_score: int
    recommendation: str
    matching_skills: List[str]
    missing_skills: List[str]
    key_strengths: List[str]
    summary_reasoning: str
    tailored_resume_tex_path: str = ""
    tailored_resume_pdf_path: Optional[str] = None
    cold_email_subject: str = ""
    cold_email_body: str = ""
    linkedin_note: str = ""
    status: str = "Saved"

class UpdateStatusRequest(BaseModel):
    """Payload to transition an application through the pipeline."""
    status: Literal["Saved", "Tailored", "Applied", "Interview", "Offer", "Rejected"]
    notes: Optional[str] = ""

class JobListItem(BaseModel):
    """Summary item for job lists and pipeline views."""
    id: int
    job_title: str
    company_name: str
    location: str
    portal_name: str
    job_url: str
    match_score: Optional[int] = None
    recommendation: Optional[str] = None
    status: str
    tailored_resume_tex_path: Optional[str] = ""
    tailored_resume_pdf_path: Optional[str] = None
    applied_at: Optional[str] = None
    created_at: str

class JobDetailResponse(BaseModel):
    """Full detail view for a specific job including evaluation, outreach, and application tracking."""
    id: int
    job_title: str
    company_name: str
    job_description: str
    location: str
    portal_name: str
    job_url: str
    salary_range: str
    match_score: Optional[int] = None
    recommendation: Optional[str] = None
    matching_skills: List[str] = []
    missing_skills: List[str] = []
    key_strengths: List[str] = []
    summary_reasoning: Optional[str] = None
    status: str = "Saved"
    tailored_resume_tex_path: str = ""
    tailored_resume_pdf_path: Optional[str] = None
    cold_email_subject: str = ""
    cold_email_body: str = ""
    linkedin_note: str = ""
    detected_email: Optional[str] = None
    notes: Optional[str] = ""
    created_at: str
    applied_at: Optional[str] = None

class PipelineMetrics(BaseModel):
    """Real-time pipeline counters for dashboard metrics cards."""
    total_jobs: int
    average_match_score: float
    ready_to_apply_count: int
    applied_count: int
    interview_count: int
    offer_count: int

class DiscoverJobsRequest(BaseModel):
    """Payload to trigger multi-portal job discovery and autonomous ingestion."""
    search_term: Optional[str] = Field(default=None, description="Target job title (e.g. 'Junior AI Engineer')")
    location: Optional[str] = Field(default=None, description="Target location or 'Remote'")
    portals: Optional[List[str]] = Field(default=["naukri"], description="List of job portals to scrape")
    results_wanted: int = Field(default=8, ge=1, le=25, description="Number of results to query per portal")
    freshness_days: Optional[int] = Field(default=1, ge=0, le=30, description="Posting freshness in days (1 = last 24 hours)")
    min_match_score: int = Field(default=75, ge=0, le=100, description="Minimum match score to mark job as Ready and tailor resume")
    max_process: int = Field(default=5, ge=1, le=15, description="Maximum new jobs to score and ingest in this run")

class ApplyWorkflowRequest(BaseModel):
    """Payload to initiate assisted or autonomous job application workflow."""
    job_id: int
    mode: Literal["assisted", "autonomous"] = Field(default="assisted", description="Assisted mode halts for human review")
    portal_name: str = Field(default="Naukri 1-Click Apply")

class ResumeWorkflowRequest(BaseModel):
    """Payload to resume an interrupted application workflow."""
    approved: bool = True
    reason: Optional[str] = None

class WorkflowStatusResponse(BaseModel):
    """Execution state of a job application workflow."""
    thread_id: str
    status: str
    is_interrupted: bool = False
    interrupt_payload: Optional[dict] = None
    review_snapshot_url: Optional[str] = None
    confirmation_snapshot_url: Optional[str] = None
    execution_logs: List[str] = []

class SaveQARequest(BaseModel):
    """Payload to save or update screening question in memory bank."""
    question: str
    answer: str
    category: str = "General"

class QAItemResponse(BaseModel):
    id: int
    question: str
    answer: str
    category: str


# =====================================================================
# Sub-Phase 5.3: Analytics, Funnel Metrics & Conversion Performance
# =====================================================================

class AnalyticsSummary(BaseModel):
    total_jobs: int
    average_match_score: float
    ready_to_apply_count: int
    applied_count: int
    interview_count: int
    offer_count: int
    archived_count: int = 0
    rejected_count: int = 0

class AnalyticsVelocity(BaseModel):
    applied_today: int
    applied_this_week: int
    applied_this_month: int

class ConversionRates(BaseModel):
    apply_rate: float
    interview_rate: float
    offer_rate: float

class ScoreDistribution(BaseModel):
    high_match: int
    viable_match: int
    low_match: int
    total_evaluated: int

class PortalMetric(BaseModel):
    portal: str
    count: int
    percentage: float

class SkillMetric(BaseModel):
    skill: str
    count: int

class SkillsInsights(BaseModel):
    top_matching_skills: List[SkillMetric] = []
    top_missing_skills: List[SkillMetric] = []

class ActivityItem(BaseModel):
    job_id: int
    job_title: str
    company_name: str
    portal_name: str
    status: str
    match_score: Optional[int] = None
    timestamp: Optional[str] = None

class DetailedAnalyticsResponse(BaseModel):
    summary: AnalyticsSummary
    velocity: AnalyticsVelocity
    conversion_rates: ConversionRates
    score_distribution: ScoreDistribution
    portals: List[PortalMetric]
    skills_insights: SkillsInsights
    recent_activity: List[ActivityItem]


# =====================================================================
# Sub-Phase 5.4: Account Connection Settings & Gmail SMTP Outreach
# =====================================================================

class TestSMTPRequest(BaseModel):
    """Payload to test Gmail SMTP credentials."""
    host: str = Field(default="smtp.gmail.com")
    port: int = Field(default=587)
    sender_email: str
    app_password: str

class SendColdEmailRequest(BaseModel):
    """Payload to send recruiter outreach email."""
    job_id: Optional[int] = None
    recipient_email: str = Field(..., description="Target recruiter or hiring manager email")
    recipient_name: Optional[str] = Field(default="Hiring Team")
    subject: str = Field(..., min_length=3)
    body: str = Field(..., min_length=10)
    resume_pdf_path: Optional[str] = None

class PortalConfigInput(BaseModel):
    username: Optional[str] = ""
    password: Optional[str] = ""

class SMTPSettingsInput(BaseModel):
    sender_email: Optional[str] = None
    sender_name: Optional[str] = None
    app_password: Optional[str] = None
    daily_limit: Optional[int] = 12
    enabled: Optional[bool] = True

class UpdateAccountSettingsRequest(BaseModel):
    """Payload to update portal accounts and SMTP configuration."""
    smtp_sender_email: Optional[str] = None
    smtp_sender_name: Optional[str] = None
    smtp_app_password: Optional[str] = None
    smtp_daily_limit: Optional[int] = None
    smtp_enabled: Optional[bool] = None
    smtp: Optional[SMTPSettingsInput] = None
    portals: Optional[dict[str, PortalConfigInput]] = None

