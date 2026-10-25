"""
Module: match.py
Purpose: Pydantic Schema for Job Matching & Scoring Results.
Standards: Rule 1 (Type Precision), Rule 2 (Strict Structured Output), Rule 3 (Concise & Accurate).
"""
from typing import List, Literal
from pydantic import BaseModel, Field

class JobMatchResult(BaseModel):
    """Structured data model returned by the AI Matching Engine."""
    job_title: str = Field(description="Extracted or inferred job title from the job description")
    company_name: str = Field(description="Extracted company name if present in JD, else 'Unknown'")
    match_score: int = Field(description="Match score percentage between 0 and 100")
    recommendation: Literal["Apply", "Review", "Skip"] = Field(
        description="'Apply' (score >= 70), 'Review' (50-69), or 'Skip' (< 50)"
    )
    matching_skills: List[str] = Field(
        description="Verified skills candidate possesses that directly match the JD"
    )
    missing_skills: List[str] = Field(
        description="Skills or keywords mentioned in JD not present in candidate profile"
    )
    key_strengths: List[str] = Field(
        description="2-3 specific bullet points from candidate experience directly relevant to this job"
    )
    summary_reasoning: str = Field(
        description="Concise 2-sentence rationale explaining the score and recommendation"
    )
