"""
Module: models.py
Purpose: SQLAlchemy ORM models for Users, Authentication, Jobs, AI Evaluations, Applications, and Q&A Knowledge.
Standards: Rule 1 (Cascading Integrity), Rule 2 (Type Constraints), Rule 3 (Concise & Readable).
"""
from datetime import datetime, timezone
from typing import List, Optional, Any
from sqlalchemy import Integer, String, Text, DateTime, ForeignKey, JSON, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship, Mapped, mapped_column

try:
    from app.db.session import Base
except ImportError:
    from .session import Base

def utc_now() -> datetime:
    """Returns timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)

class User(Base):
    """User account model for multi-tenant authentication and profile ownership."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    jobs: Mapped[List["Job"]] = relationship("Job", back_populates="user", cascade="all, delete-orphan")
    applications: Mapped[List["Application"]] = relationship("Application", back_populates="user", cascade="all, delete-orphan")
    reset_otps: Mapped[List["PasswordResetOTP"]] = relationship("PasswordResetOTP", back_populates="user", cascade="all, delete-orphan")

class PasswordResetOTP(Base):
    """Stores temporary 6-digit cryptographic OTPs for user password recovery."""
    __tablename__ = "password_reset_otps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    otp_code: Mapped[str] = mapped_column(String(10), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    user: Mapped["User"] = relationship("User", back_populates="reset_otps")

class Job(Base):
    """Stores raw job listings discovered through scraping or manual entry."""
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
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
    user: Mapped[Optional["User"]] = relationship("User", back_populates="jobs")
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
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
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

    user: Mapped[Optional["User"]] = relationship("User", back_populates="applications")
    job: Mapped["Job"] = relationship("Job", back_populates="applications")

class ApplicationAnswer(Base):
    """Stores verified answers for repeated screening questions across application portals."""
    __tablename__ = "application_answers"
    __table_args__ = (UniqueConstraint("user_id", "question", name="uq_user_question"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    question: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), default="General")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
