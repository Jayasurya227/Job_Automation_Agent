"""
Module: outreach.py
Purpose: Pydantic Schema for Cold Outreach (Emails & LinkedIn Notes).
Standards: Rule 1 (Type Precision), Rule 2 (Strict Structured Output), Rule 3 (Concise & Accurate).
"""
from typing import Literal
from pydantic import BaseModel, Field

class OutreachPackage(BaseModel):
    """Structured data model returned by the Outreach Generator."""
    target_persona: Literal["Technical_Lead", "HR_Recruiter"] = Field(
        description="The persona this outreach was tailored for: Technical_Lead or HR_Recruiter"
    )
    subject_line: str = Field(
        description="Punchy, professional email subject line under 9 words with high open-rate potential"
    )
    cold_email_body: str = Field(
        description="Personalized cold email body between 60 and 90 words connecting candidate metrics to the role"
    )
    linkedin_connection_note: str = Field(
        description="Concise LinkedIn connection invitation message strictly under 280 characters"
    )
    highlighted_project: str = Field(
        description="The specific project from candidate profile chosen as the primary technical hook"
    )
    call_to_action: str = Field(
        description="Low-friction closing ask (e.g., brief 5-minute chat, open to reviewing resume)"
    )
