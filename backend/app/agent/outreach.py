"""
Module: outreach.py
Purpose: Step 1.5 Cold Outreach Generator - Generates personalized emails & LinkedIn notes.
Standards: Rule 1 (Persona Tuning & Grounding), Rule 2 (Pydantic Schema),
           Rule 3 (Concise & Accurate), Rule 4 (Standard Layout), Rule 5 (Production Dynamic).
"""
import json
import warnings
from typing import Literal

warnings.filterwarnings("ignore", category=FutureWarning)
from dotenv import load_dotenv
from google.genai import types

from app.config import DEFAULT_MODEL, gemini_client
from app.utils.rate_limiter import execute_with_rate_limit
from app.schemas.match import JobMatchResult
from app.schemas.outreach import OutreachPackage
from app.agent.scorer import load_profile

def generate_outreach(
    job_description: str,
    match_result: JobMatchResult,
    recipient_name: str = "Hiring Team",
    recipient_role: Literal["Technical_Lead", "HR_Recruiter"] = "Technical_Lead",
    profile_path: str = "profile.json",
    model_name: str = DEFAULT_MODEL
) -> OutreachPackage:
    """
    Generates personalized cold emails and LinkedIn connection notes tailored to the recipient persona.
    """
    load_dotenv()
    profile = load_profile(profile_path)

    # Use the global gemini_client from config (already initialized with API key)
    safety_settings = [
        types.SafetySetting(
            category="HARM_CATEGORY_DANGEROUS_CONTENT",
            threshold="BLOCK_ONLY_HIGH",
        ),
    ]

    # Persona-specific guidelines
    if recipient_role == "Technical_Lead":
        persona_context = (
            "RECIPIENT: Engineering Manager / Tech Lead / CTO.\n"
            "TONE: Peer-to-peer, technical, metric-driven.\n"
            "FOCUS: Highlight specific engineering challenges solved (e.g. sub-second semantic Video RAG retrieval, "
            "FastAPI backend architecture, or Playwright scraping pipeline).\n"
        )
    else:
        persona_context = (
            "RECIPIENT: Talent Acquisition Partner / HR Recruiter.\n"
            "TONE: Courteous, professional, crisp.\n"
            "FOCUS: Highlight notice period (Immediate joiner), location flexibility (Remote/Hybrid), "
            "verified startup experience, and exact tech stack alignment with the JD.\n"
        )

    system_instruction = (
        "You are an executive career coach and cold outreach copywriting specialist.\n"
        "Your task is to write high-converting, personalized cold outreach for a job applicant.\n\n"
        f"{persona_context}\n"
        "CRITICAL WRITING RULES:\n"
        "1. NO SPAM CLICHE: Never start with 'I hope this email finds you well' or 'My name is...'.\n"
        "2. CONCISE BREVITY: The email body must be between 60 and 90 words. Busy executives ignore long emails.\n"
        "3. LINKEDIN LIMIT: The linkedin_connection_note must be strictly under 280 characters.\n"
        "4. STRICT TRUTH: Reference only real projects and verified skills from the Candidate Profile.\n"
        "5. LOW-FRICTION CTA: End with a polite, non-demanding 5-minute question (e.g., 'Are you open to a brief chat?').\n"
    )

    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        response_mime_type="application/json",
        response_schema=OutreachPackage,
        temperature=0.3,
        safety_settings=safety_settings,
    )

    prompt = (
        f"--- CANDIDATE PROFILE ---\n"
        f"{profile.model_dump_json(indent=2)}\n\n"
        f"--- TARGET ROLE & MATCH DETAILS ---\n"
        f"Target Role: {match_result.job_title} at {match_result.company_name}\n"
        f"Matching Skills: {', '.join(match_result.matching_skills)}\n"
        f"Recipient Name: {recipient_name}\n"
        f"Recipient Persona: {recipient_role}\n\n"
        f"--- JOB DESCRIPTION ---\n"
        f"{job_description.strip()}\n"
    )

    # Execute AI Generation with Rate-Limiting Protection
    response = execute_with_rate_limit(
        gemini_client.models.generate_content,
        model=model_name,
        contents=prompt,
        config=config,
    )
    
    # Guardrails & Safety check (Rule 1 & Rule 5)
    if not response.candidates:
        raise RuntimeError("AI model returned no candidates. Content may have been blocked.")
    candidate = response.candidates[0]
    finish_reason = getattr(candidate, "finish_reason", None)
    if finish_reason and str(finish_reason) not in ("STOP", "FinishReason.STOP", "1"):
        raise RuntimeError(f"AI generation stopped unexpectedly. Finish reason: {finish_reason}")

    try:
        raw_data = json.loads(response.text)
        if not isinstance(raw_data, dict):
            raw_data = {}
    except Exception:
        raw_data = {}

    skill_str = ", ".join(match_result.matching_skills[:3]) if match_result.matching_skills else "Python & AI Engineering"
    top_project = profile.projects[0].title if profile.projects else "Full Stack & AI Projects"

    if not raw_data.get("target_persona"):
        raw_data["target_persona"] = recipient_role
    if not raw_data.get("subject_line"):
        raw_data["subject_line"] = f"Application: {match_result.job_title} - Jai ({skill_str})"
    if not raw_data.get("cold_email_body"):
        raw_data["cold_email_body"] = (
            f"Dear {recipient_name},\n\n"
            f"I came across the {match_result.job_title} opening at {match_result.company_name}. "
            f"With hands-on experience in {skill_str} and building production systems like {top_project}, "
            f"I am eager to contribute to your engineering goals. As an immediate joiner, I would love to discuss how I can add immediate value.\n\n"
            f"Best regards,\nJai"
        )
    if not raw_data.get("linkedin_connection_note"):
        raw_data["linkedin_connection_note"] = (
            f"Hi {recipient_name}, saw the {match_result.job_title} opening at {match_result.company_name}. "
            f"With hands-on experience in {skill_str}, I would love to connect!"
        )[:280]
    if not raw_data.get("highlighted_project"):
        raw_data["highlighted_project"] = top_project
    if not raw_data.get("call_to_action"):
        raw_data["call_to_action"] = "Open to a brief 5-minute introductory conversation this week?"

    return OutreachPackage(**raw_data)
