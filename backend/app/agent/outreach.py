"""
Module: outreach.py
Purpose: Recruiter Cold Outreach Generator (Disabled per user request).
Safely provides no-op stub so existing imports and data models remain unbroken
while completely removing all Gemini AI API calls and cold email generation.
"""
from typing import Any, Literal
from app.schemas.match import JobMatchResult
from app.schemas.outreach import OutreachPackage


def generate_outreach(
    job_description: str = "",
    match_result: Any = None,
    recipient_name: str = "Hiring Team",
    recipient_role: Literal["Technical_Lead", "HR_Recruiter"] = "HR_Recruiter",
    profile_path: str = "profile.json",
    model_name: str = ""
) -> OutreachPackage:
    """
    Disabled per user preference to focus agent resources strictly on automated job applications.
    Returns an empty OutreachPackage without invoking Gemini API.
    """
    return OutreachPackage(
        recipient_role=recipient_role,
        highlighted_project="",
        subject_line="",
        cold_email_body="",
        linkedin_connection_note="",
        call_to_action=""
    )
