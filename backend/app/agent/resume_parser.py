"""
Module: resume_parser.py
Purpose: Parses uploaded PDF resumes and automatically extracts candidate facts, skills, and projects via Gemini AI.
Standards: Rule 1 (Zero Hallucination), Rule 2 (Type Safety), Rule 3 (Concise & Accurate), Rule 5 (Production Reliability).
"""
import io
import json
import logging
import re
from typing import Dict, Any, Optional
import pypdf
import google.generativeai as genai
from app.config import DEFAULT_MODEL, BASE_DIR, DATA_DIR
from app.schemas.profile import CandidateProfile

logger = logging.getLogger("agent.resume_parser")

PROFILE_FILE = BASE_DIR / "profile.json"
UPLOADED_RESUME_FILE = DATA_DIR / "uploaded_resume.pdf"


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extracts raw text from PDF binary content using pypdf."""
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    extracted = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            extracted.append(text.strip())
    return "\n\n".join(extracted).strip()


def parse_resume_content(
    resume_text: str,
    existing_profile_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Parses resume text using Gemini AI into structured CandidateProfile schema,
    preserving existing search preferences and notice period settings.
    """
    if not resume_text or len(resume_text.strip()) < 30:
        raise ValueError("Resume text is too short or empty to extract meaningful profile information.")

    system_instruction = (
        "You are an elite executive resume parser and talent analyst.\n"
        "Your task is to extract accurate, verified information from the candidate's resume text.\n"
        "CRITICAL RULES:\n"
        "1. Extract the candidate's full legal name, email, phone number, location, and social links (GitHub, LinkedIn, Portfolio).\n"
        "2. Extract technical skills into categories: programming_languages, frameworks_and_libraries, ai_and_ml, databases, tools_and_platforms.\n"
        "3. Extract work experiences: role, company, location, dates, and bullet highlights.\n"
        "4. Extract projects: title, tech_stack, description, key_achievements, live_url, github_url.\n"
        "5. Extract education: degree, field_of_study, institution, graduation_year.\n"
        "6. ZERO HALLUCINATION: Only include facts explicitly mentioned in the resume text.\n"
    )

    model = genai.GenerativeModel(
        model_name=DEFAULT_MODEL,
        system_instruction=system_instruction,
        generation_config={
            "response_mime_type": "application/json",
            "temperature": 0.1,
        }
    )

    prompt = (
        f"Extract all information from the following resume text into a JSON object matching this schema:\n\n"
        f"Schema Example:\n"
        f"{{\n"
        f'  "personal_info": {{\n'
        f'    "name": "Full Name",\n'
        f'    "email": "email@example.com",\n'
        f'    "phone": "+91-XXXXXXXXXX",\n'
        f'    "location": "City, Country",\n'
        f'    "linkedin_url": "",\n'
        f'    "github_url": "",\n'
        f'    "portfolio_url": ""\n'
        f"  }},\n"
        f'  "technical_skills": {{\n'
        f'    "programming_languages": ["Python", "JavaScript"],\n'
        f'    "frameworks_and_libraries": ["FastAPI", "React"],\n'
        f'    "ai_and_ml": ["LLMs", "RAG", "LangChain"],\n'
        f'    "databases": ["SQLite", "PostgreSQL"],\n'
        f'    "tools_and_platforms": ["Git", "Docker"]\n'
        f"  }},\n"
        f'  "experience": [\n'
        f'    {{\n'
        f'      "role": "Role Title",\n'
        f'      "company": "Company Name",\n'
        f'      "location": "City",\n'
        f'      "start_date": "MM/YYYY",\n'
        f'      "end_date": "Present",\n'
        f'      "is_current": true,\n'
        f'      "highlights": ["Accomplished X using Y"]\n'
        f'    }}\n'
        f"  ],\n"
        f'  "projects": [\n'
        f'    {{\n'
        f'      "title": "Project Name",\n'
        f'      "tech_stack": ["Python", "FastAPI"],\n'
        f'      "description": "Short project summary",\n'
        f'      "key_achievements": ["Achievement bullet"],\n'
        f'      "live_url": "",\n'
        f'      "github_url": ""\n'
        f'    }}\n'
        f"  ],\n"
        f'  "education": [\n'
        f'    {{\n'
        f'      "degree": "B.Tech",\n'
        f'      "field_of_study": "Computer Science",\n'
        f'      "institution": "University",\n'
        f'      "graduation_year": 2025\n'
        f'    }}\n'
        f"  ]\n"
        f"}}\n\n"
        f"--- RESUME TEXT ---\n"
        f"{resume_text}"
    )

    response = model.generate_content(prompt)
    raw_content = response.text.strip()

    # Strip code block wrappers if present
    if raw_content.startswith("```"):
        raw_content = re.sub(r"^```(?:json)?\s*", "", raw_content)
        raw_content = re.sub(r"\s*```$", "", raw_content)

    parsed = json.loads(raw_content)

    # Base profile to preserve preferences
    base = existing_profile_data or {}
    if not base and PROFILE_FILE.exists():
        try:
            with open(PROFILE_FILE, "r", encoding="utf-8") as f:
                base = json.load(f)
        except Exception:
            base = {}

    # Merge extracted details while keeping preferences intact
    merged = {
        "personal_info": {
            **base.get("personal_info", {}),
            **parsed.get("personal_info", {})
        },
        "preferences": base.get("preferences", {
            "target_roles": ["Junior AI Engineer", "Python Developer"],
            "preferred_locations": ["India", "Remote"],
            "work_modes": ["Remote", "Hybrid"],
            "min_expected_salary": "Negotiable / Standard Industry CTC",
            "notice_period_days": 0
        }),
        "technical_skills": {
            **base.get("technical_skills", {}),
            **parsed.get("technical_skills", {})
        },
        "experience": parsed.get("experience", base.get("experience", [])),
        "projects": parsed.get("projects", base.get("projects", [])),
        "education": parsed.get("education", base.get("education", [])),
        "application_answers": base.get("application_answers", {
            "immediate_joiner": True,
            "willing_to_relocate": True,
            "years_of_experience": 1.0,
            "work_authorization": "Authorized to work in India",
            "custom_qa": {}
        })
    }

    # Validate against CandidateProfile Pydantic schema
    validated = CandidateProfile(**merged)
    data = validated.model_dump()

    # Save to profile.json
    with open(PROFILE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    logger.info("Successfully parsed resume and synced with profile.json.")
    return data
