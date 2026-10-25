"""
Module: scorer.py
Purpose: Step 1.3 AI Brain - Analyzes and scores Job Descriptions against Candidate Profile.
Standards: Rule 1 (Anti-Hallucination Guardrails), Rule 2 (Pydantic Schema Enforcement),
           Rule 3 (Concise & Modular), Rule 4 (Structured Directory), Rule 5 (Production Standard).
"""
import json
from pathlib import Path

from google.genai import types

from app.config import DEFAULT_MODEL, gemini_client
from app.utils.rate_limiter import execute_with_rate_limit
from app.schemas.profile import CandidateProfile
from app.schemas.match import JobMatchResult

def load_profile(profile_path: str = "profile.json") -> CandidateProfile:
    """Dynamically loads and validates candidate profile from disk."""
    target = Path(profile_path)
    if not target.exists():
        raise FileNotFoundError(f"Profile not found at: {profile_path}")
    with open(target, "r", encoding="utf-8") as f:
        data = json.load(f)
    return CandidateProfile(**data)

def analyze_and_score_job(
    job_description: str,
    profile_path: str = "profile.json",
    model_name: str = DEFAULT_MODEL
) -> JobMatchResult:
    """
    Evaluates a raw Job Description against the Candidate Profile using Gemini.
    Enforces pure JSON output matching JobMatchResult Pydantic schema.
    """
    # config.py is the single configuration boundary — it already calls
    # genai.configure(api_key=GEMINI_API_KEY) at import time. No re-configuration needed here.

    # 1. Load dynamic candidate profile (Rule 5: Always fresh data)
    profile = load_profile(profile_path)

    # 2. Configure Safety Settings (Rule 4: Avoid false blocks on technical terms)
    safety_settings = [
        types.SafetySetting(
            category="HARM_CATEGORY_DANGEROUS_CONTENT",
            threshold="BLOCK_ONLY_HIGH",
        ),
        types.SafetySetting(
            category="HARM_CATEGORY_HARASSMENT",
            threshold="BLOCK_ONLY_HIGH",
        ),
    ]

    # 4. Strict Grounded System Prompt (Rule 1: Anti-Hallucination)
    system_instruction = (
        "You are an objective, senior technical recruiter and ATS evaluation engine.\n"
        "Your task is to accurately score a Job Description against a verified Candidate Profile.\n\n"
        "CRITICAL GROUNDING RULES:\n"
        "1. STRICT TRUTH: You must ONLY evaluate skills and achievements explicitly stated in the Candidate Profile.\n"
        "2. NO FABRICATION: Never invent, extrapolate, or assume skills the candidate has not listed.\n"
        "3. ACCURATE SCORING:\n"
        "   - Score 80-100: Candidate has all primary required skills and relevant projects.\n"
        "   - Score 60-79: Candidate has core programming languages and frameworks but lacks 1-2 nice-to-have tools.\n"
        "   - Score 0-59: Candidate lacks primary core requirements or required years of experience.\n"
        "4. RECOMMENDATION LOGIC:\n"
        "   - 'Apply' if match_score >= 70\n"
        "   - 'Review' if match_score is between 50 and 69\n"
        "   - 'Skip' if match_score < 50\n"
    )

    # 3. Build generation config
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        response_mime_type="application/json",
        response_schema=JobMatchResult,
        temperature=0.2,
        safety_settings=safety_settings,
    )

    # 4. Construct prompt payload
    prompt = (
        f"--- CANDIDATE PROFILE ---\n"
        f"{profile.model_dump_json(indent=2)}\n\n"
        f"--- TARGET JOB DESCRIPTION ---\n"
        f"{job_description.strip()}\n"
    )

    # 5. Execute AI Generation with Rate-Limiting Protection
    response = execute_with_rate_limit(
        gemini_client.models.generate_content,
        model=model_name,
        contents=prompt,
        config=config,
    )
    
    # 8. Guardrails & Safety check (Rule 1 & Rule 5)
    if not response.candidates:
        raise RuntimeError("AI model returned no candidates. Content may have been blocked.")
    
    candidate = response.candidates[0]
    finish_reason = getattr(candidate, "finish_reason", None)
    if finish_reason and str(finish_reason) not in ("STOP", "FinishReason.STOP", "1"):
        raise RuntimeError(f"AI generation stopped unexpectedly. Finish reason: {finish_reason}")

    # 9. Parse into Pydantic schema (Rule 2: Type validation)
    result_data = json.loads(response.text)
    return JobMatchResult(**result_data)
