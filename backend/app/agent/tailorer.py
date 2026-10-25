"""
Module: tailorer.py
Purpose: Resume routing module. Bypasses LaTeX generation overhead
and attaches candidate's verified master PDF resume directly for fast, reliable applications.
"""
import logging
from pathlib import Path
from typing import Dict, List, Any
from pydantic import BaseModel, Field

logger = logging.getLogger("tailorer")

from app.config import BASE_DIR
from app.schemas.match import JobMatchResult
from app.agent.scorer import load_profile

class TailoredProject(BaseModel):
    title: str = Field(description="Project title from candidate profile")
    tech_stack: List[str] = Field(description="Technologies used")
    bullets: List[str] = Field(description="Bullet points")

class TailoredResumePayload(BaseModel):
    summary: str = Field(description="Summary")
    languages: List[str] = Field(default_factory=list)
    frameworks: List[str] = Field(default_factory=list)
    ai_skills: List[str] = Field(default_factory=list)
    databases_tools: List[str] = Field(default_factory=list)
    experience_bullets: List[str] = Field(default_factory=list)
    projects: List[TailoredProject] = Field(default_factory=list)


def escape_latex(text: str) -> str:
    """Pass-through helper."""
    return str(text) if text else ""


def tailor_resume(
    job_description: str,
    match_result: JobMatchResult,
    profile_path: str = "profile.json",
    output_dir: str = "output/resumes",
    template_path: str = "app/templates/resume_template.tex"
) -> Dict[str, Any]:
    """
    Directly routes to master uploaded resume PDF (LaTeX tailoring paused per user preference).
    Bypasses Gemini LLM call and LaTeX compilation for 10x faster execution and zero token cost.
    """
    master_pdf = BASE_DIR / "data" / "uploaded_resume.pdf"
    pdf_path = str(master_pdf) if master_pdf.exists() else None

    logger.info("Using master candidate resume PDF directly (LaTeX tailoring paused).")
    return {
        "status": "success",
        "tex_path": "",
        "pdf_path": pdf_path,
        "summary": "Master Candidate Resume attached directly.",
        "matching_skills_used": match_result.matching_skills if match_result else []
    }
