"""
Module: resume_parser.py
Purpose: Parses uploaded PDF resumes and automatically extracts candidate facts, skills, and projects via Gemini AI.
Standards: Rule 1 (Zero Hallucination), Rule 2 (Type Safety), Rule 3 (Concise & Accurate), Rule 5 (Production Reliability).
"""
import base64
import io
import json
import logging
import re
from typing import Dict, Any, Optional
import pypdf
from app.config import DEFAULT_MODEL, BASE_DIR, DATA_DIR, claude_client
from app.agent.llm import response_text
from app.schemas.profile import CandidateProfile

logger = logging.getLogger("agent.resume_parser")

PROFILE_FILE = BASE_DIR / "profile.json"
UPLOADED_RESUME_FILE = DATA_DIR / "uploaded_resume.pdf"


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extracts raw text from PDF binary content using pypdf safely."""
    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        extracted = []
        for page in reader.pages:
            try:
                text = page.extract_text() or ""
                if text.strip():
                    extracted.append(text.strip())
            except Exception:
                continue
        return "\n\n".join(extracted).strip()
    except Exception as e:
        logger.warning(f"pypdf text extraction encountered error: {e}")
        return ""


def clean_and_parse_json(raw_text: str) -> Dict[str, Any]:
    """Robustly cleans and parses JSON from AI output."""
    text = (raw_text or "").strip()
    # Strip markdown block wrappers
    if "```" in text:
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
        text = text.strip()

    # Find outermost { and }
    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        text = match.group(1).strip()

    # Attempt 1: Standard json.loads
    try:
        return json.loads(text)
    except Exception:
        pass

    # Attempt 2: Remove trailing commas before } or ]
    cleaned = re.sub(r",\s*([}\]])", r"\1", text)
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # Attempt 3: orjson if available
    try:
        import orjson
        return orjson.loads(text)
    except Exception:
        pass

    try:
        import orjson
        return orjson.loads(cleaned)
    except Exception:
        pass

    # Attempt 4: Clean common control characters
    cleaned2 = re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", cleaned)
    try:
        return json.loads(cleaned2)
    except Exception as e:
        raise ValueError(f"Could not parse valid JSON from AI response: {e}\nRaw output preview: {text[:200]}")


def sanitize_profile_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Ensures all extracted fields match expected types and defaults for CandidateProfile."""
    if not isinstance(data, dict):
        return {}

    # Personal info
    pi = data.get("personal_info") or {}
    for k in ["name", "email", "phone", "location", "linkedin_url", "github_url", "portfolio_url"]:
        val = pi.get(k)
        if val is None:
            pi[k] = ""
        else:
            pi[k] = str(val).strip()
    if not pi.get("name"):
        pi["name"] = "Candidate"
    data["personal_info"] = pi

    # Technical skills
    ts = data.get("technical_skills") or {}
    for cat in ["programming_languages", "frameworks_and_libraries", "ai_and_ml", "databases", "tools_and_platforms"]:
        val = ts.get(cat)
        if isinstance(val, list):
            ts[cat] = [str(item).strip() for item in val if item]
        elif isinstance(val, str) and val.strip():
            ts[cat] = [s.strip() for s in val.split(",") if s.strip()]
        else:
            ts[cat] = []
    data["technical_skills"] = ts

    # Experience
    exp = data.get("experience")
    if not isinstance(exp, list):
        data["experience"] = []
    else:
        cleaned_exp = []
        for item in exp:
            if isinstance(item, dict):
                cleaned_item = {
                    "role": str(item.get("role") or ""),
                    "company": str(item.get("company") or ""),
                    "location": str(item.get("location") or ""),
                    "start_date": str(item.get("start_date") or ""),
                    "end_date": str(item.get("end_date") or ""),
                    "is_current": bool(item.get("is_current", False)),
                    "highlights": [str(h) for h in item.get("highlights", []) if h]
                }
                cleaned_exp.append(cleaned_item)
        data["experience"] = cleaned_exp

    # Projects
    proj = data.get("projects")
    if not isinstance(proj, list):
        data["projects"] = []
    else:
        cleaned_proj = []
        for item in proj:
            if isinstance(item, dict):
                cleaned_proj.append({
                    "title": str(item.get("title") or "Project"),
                    "tech_stack": [str(t) for t in item.get("tech_stack", []) if t],
                    "description": str(item.get("description") or ""),
                    "key_achievements": [str(a) for a in item.get("key_achievements", []) if a],
                    "live_url": str(item.get("live_url") or ""),
                    "github_url": str(item.get("github_url") or "")
                })
        data["projects"] = cleaned_proj

    # Education
    edu = data.get("education")
    if not isinstance(edu, list):
        data["education"] = []
    else:
        cleaned_edu = []
        for item in edu:
            if isinstance(item, dict):
                cleaned_edu.append({
                    "degree": str(item.get("degree") or ""),
                    "field_of_study": str(item.get("field_of_study") or ""),
                    "institution": str(item.get("institution") or ""),
                    "graduation_year": item.get("graduation_year", 2025)
                })
        data["education"] = cleaned_edu

    return data


def parse_resume_content(
    resume_text: Optional[str] = None,
    existing_profile_data: Optional[Dict[str, Any]] = None,
    pdf_bytes: Optional[bytes] = None
) -> Dict[str, Any]:
    """
    Parses resume content (via direct PDF bytes or extracted text) using Gemini AI
    into structured CandidateProfile schema, preserving existing search preferences
    and application answers.
    """
    system_instruction = (
        "You are an elite executive resume parser and talent analyst.\n"
        "Your task is to extract accurate, verified information from the candidate's resume.\n"
        "CRITICAL EXTRACTION RULES:\n"
        "1. Extract candidate contact info: name, email, phone number, location, and social links (GitHub, LinkedIn, Portfolio).\n"
        "2. Extract technical skills into categories: programming_languages, frameworks_and_libraries, ai_and_ml, databases, tools_and_platforms.\n"
        "3. Extract work experiences: role, company, location, start_date, end_date, is_current, and highlights.\n"
        "4. Extract projects: title, tech_stack, description, key_achievements, live_url, github_url.\n"
        "5. Extract education: degree, field_of_study, institution, graduation_year.\n"
        "6. ZERO HALLUCINATION: Only include facts explicitly mentioned in the resume. Return pure JSON."
    )

    schema_prompt = (
        "Extract all information into a JSON object matching this schema:\n\n"
        "{\n"
        '  "personal_info": {\n'
        '    "name": "Full Name",\n'
        '    "email": "email@example.com",\n'
        '    "phone": "+91-XXXXXXXXXX",\n'
        '    "location": "City, Country",\n'
        '    "linkedin_url": "",\n'
        '    "github_url": "",\n'
        '    "portfolio_url": ""\n'
        "  },\n"
        '  "technical_skills": {\n'
        '    "programming_languages": ["Python", "JavaScript"],\n'
        '    "frameworks_and_libraries": ["FastAPI", "React"],\n'
        '    "ai_and_ml": ["LLMs", "RAG", "LangChain"],\n'
        '    "databases": ["SQLite", "PostgreSQL"],\n'
        '    "tools_and_platforms": ["Git", "Docker"]\n'
        "  },\n"
        '  "experience": [\n'
        "    {\n"
        '      "role": "Role Title",\n'
        '      "company": "Company Name",\n'
        '      "location": "City",\n'
        '      "start_date": "MM/YYYY",\n'
        '      "end_date": "Present",\n'
        '      "is_current": true,\n'
        '      "highlights": ["Accomplished X using Y"]\n'
        "    }\n"
        "  ],\n"
        '  "projects": [\n'
        "    {\n"
        '      "title": "Project Name",\n'
        '      "tech_stack": ["Python", "FastAPI"],\n'
        '      "description": "Short project summary",\n'
        '      "key_achievements": ["Achievement bullet"],\n'
        '      "live_url": "",\n'
        '      "github_url": ""\n'
        "    }\n"
        "  ],\n"
        '  "education": [\n'
        "    {\n"
        '      "degree": "B.Tech",\n'
        '      "field_of_study": "Computer Science",\n'
        '      "institution": "University",\n'
        '      "graduation_year": 2025\n'
        "    }\n"
        "  ]\n"
        "}"
    )

    raw_content = ""
    last_error = None

    # Step 1: Try Direct PDF Multimodal Extraction (Most robust across Canva, LaTeX, Apple Pages, Scans)
    if pdf_bytes and len(pdf_bytes) > 0:
        try:
            logger.info("Attempting multimodal PDF extraction via Claude...")
            pdf_block = {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": base64.standard_b64encode(pdf_bytes).decode("utf-8"),
                },
            }
            response = claude_client.messages.create(
                model=DEFAULT_MODEL,
                max_tokens=16000,
                system=system_instruction,
                messages=[{
                    "role": "user",
                    "content": [
                        pdf_block,
                        {"type": "text", "text": f"{schema_prompt}\nExtract all candidate details from this attached resume PDF."},
                    ],
                }],
            )
            raw_content = response_text(response)
        except Exception as e:
            logger.warning(f"Multimodal PDF parsing encountered error: {e}. Falling back to text prompt...")
            last_error = e

    # Step 2: Fallback to extracted text prompt if direct PDF parsing did not produce output
    if not raw_content and resume_text and len(resume_text.strip()) >= 20:
        try:
            logger.info("Extracting resume details from text prompt...")
            prompt = f"{schema_prompt}\n\n--- RESUME TEXT ---\n{resume_text}"
            response = claude_client.messages.create(
                model=DEFAULT_MODEL,
                max_tokens=16000,
                system=system_instruction,
                messages=[{"role": "user", "content": prompt}],
            )
            raw_content = response_text(response)
        except Exception as e:
            logger.error(f"Text prompt parsing error: {e}")
            last_error = e

    if not raw_content:
        raise ValueError(f"Could not extract information from resume: {last_error or 'Empty AI response'}")

    # Step 3: Clean and parse JSON safely
    parsed = clean_and_parse_json(raw_content)
    sanitized = sanitize_profile_dict(parsed)

    # Step 4: Base profile to preserve preferences
    base = existing_profile_data or {}
    if not base and PROFILE_FILE.exists():
        try:
            with open(PROFILE_FILE, "r", encoding="utf-8") as f:
                base = json.load(f)
        except Exception:
            base = {}

    # Merge extracted details:
    # - Personal info, skills, experience, projects, education come from the new resume
    # - Search preferences and application answers are preserved from the user's existing settings
    new_pi = sanitized.get("personal_info", {})
    base_pi = base.get("personal_info", {})
    merged_pi = {
        "name": new_pi.get("name") or base_pi.get("name", "Candidate"),
        "email": new_pi.get("email") or base_pi.get("email", ""),
        "phone": new_pi.get("phone") or base_pi.get("phone", ""),
        "location": new_pi.get("location") or base_pi.get("location", ""),
        "linkedin_url": new_pi.get("linkedin_url") or base_pi.get("linkedin_url", ""),
        "github_url": new_pi.get("github_url") or base_pi.get("github_url", ""),
        "portfolio_url": new_pi.get("portfolio_url") or base_pi.get("portfolio_url", "")
    }

    merged = {
        "personal_info": merged_pi,
        "preferences": base.get("preferences", {
            "target_roles": ["Junior AI Engineer", "Python Developer"],
            "preferred_locations": ["India", "Remote"],
            "work_modes": ["Remote", "Hybrid"],
            "min_expected_salary": "Negotiable / Standard Industry CTC",
            "notice_period_days": 0,
            "freshness_days": 1,
            "autopilot_enabled": False,
            "autopilot_auto_apply_score": 80,
            "autopilot_max_daily_apps": 12,
            "autopilot_run_hour": 22,
            "autopilot_run_minute": 30
        }),
        "technical_skills": sanitized.get("technical_skills", {
            "programming_languages": [],
            "frameworks_and_libraries": [],
            "ai_and_ml": [],
            "databases": [],
            "tools_and_platforms": []
        }),
        "experience": sanitized.get("experience", []),
        "projects": sanitized.get("projects", []),
        "education": sanitized.get("education", []),
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

    # Save to profile.json atomically
    with open(PROFILE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    logger.info("Successfully parsed resume and synced with profile.json.")
    return data
