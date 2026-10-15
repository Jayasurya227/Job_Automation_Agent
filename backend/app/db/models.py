"""
Module: models.py
Purpose: SQLAlchemy ORM models for Jobs, AI Evaluations, Applications, and Q&A Knowledge.
Standards: Rule 1 (Cascading Integrity), Rule 2 (Type Constraints), Rule 3 (Concise & Readable).
"""
from datetime import datetime, timezone
from typing import List, Optional, Any
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship, Mapped, mapped_column

try:
    from app.db.session import Base
except ImportError:
    from .session import Base

def utc_now() -> datetime:
    """Returns timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)

class Job(Base):
    """Stores raw job listings discovered through scraping or manual entry."""
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    location: Mapped[str] = mapped_column(String(255), default="")
    portal_name: Mapped[str] = mapped_column(String(100), default="Manual")
    job_url: Mapped[str] = mapped_column(String(1024), default="")
    job_description: Mapped[str] = mapped_column(Text, nullable=False)
    salary_range: Mapped[str] = mapped_column(String(100), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships with cascading delete to prevent orphan records
    evaluation: Mapped[Optional["JobEvaluation"]] = relationship("JobEvaluation", back_populates="job", uselist=False, cascade="all, delete-orphan")
    applications: Mapped[List["Application"]] = relationship("Application", back_populates="job", cascade="all, delete-orphan")

class JobEvaluation(Base):
    """Stores AI scoring, fit percentage, and match reasoning from Step 1.3."""
    __tablename__ = "job_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    match_score: Mapped[int] = mapped_column(Integer, nullable=False)
    recommendation: Mapped[str] = mapped_column(String(50), nullable=False)
    matching_skills: Mapped[Any] = mapped_column(JSON, nullable=False, default=list)
    missing_skills: Mapped[Any] = mapped_column(JSON, nullable=False, default=list)
    key_strengths: Mapped[Any] = mapped_column(JSON, nullable=False, default=list)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    job: Mapped["Job"] = relationship("Job", back_populates="evaluation")

class Application(Base):
    """Tracks application pipeline stage, tailored resume paths, and cold outreach text."""
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), default="Saved", index=True)  # Saved, Tailored, Applied, Interview, Offer, Rejected
    tailored_resume_tex_path: Mapped[str] = mapped_column(String(512), default="")
    tailored_resume_pdf_path: Mapped[str] = mapped_column(String(512), default="")
    cold_email_subject: Mapped[str] = mapped_column(String(255), default="")
    cold_email_body: Mapped[str] = mapped_column(Text, default="")
    linkedin_note: Mapped[str] = mapped_column(String(512), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    job: Mapped["Job"] = relationship("Job", back_populates="applications")

class ApplicationAnswer(Base):
    """Stores verified answers for repeated screening questions across application portals."""
    __tablename__ = "application_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    question: Mapped[str] = mapped_column(String(512), unique=True, nullable=False, index=True)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), default="General")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
