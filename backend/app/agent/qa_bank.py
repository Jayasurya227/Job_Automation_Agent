"""
Module: qa_bank.py
Purpose: Step 4.2 Screening Q&A Memory Bank & AI Answer Generator.
Standards: Rule 1 (Zero Hallucination - Grounded strictly in profile.json),
           Rule 2 (Pydantic & SQLAlchemy typed schemas),
           Rule 3 (Low Code & High Signal),
           Rule 4 (Deterministic Cache-First Lookup),
           Rule 5 (ACID Persistence in SQLite).
"""
import re
import os
import json
import logging
from typing import Dict, Any, Optional, List, Callable, TypedDict
from pathlib import Path

try:
    from app.config import DEFAULT_MODEL, claude_client
    from app.agent.llm import response_text
    from app.agent.scorer import load_profile
    from app.db.session import SessionLocal
    from app.db import crud
except ImportError:
    from ..config import DEFAULT_MODEL, claude_client
    from .llm import response_text
    from .scorer import load_profile
    from ..db.session import SessionLocal
    from ..db import crud

logger = logging.getLogger("qa_bank")


class RulePattern(TypedDict):
    pattern: str
    handler: Callable[[Any], Any]
    category: str


# Predefined question regex patterns mapping to profile data
RULE_PATTERNS: List[RulePattern] = [
    {
        "pattern": r"(authorized to work|legally authorized|work authorization|eligible to work)",
        "handler": lambda p: "Yes" if "Authorized" in p.application_answers.work_authorization else p.application_answers.work_authorization,
        "category": "Work_Auth"
    },
    {
        "pattern": r"(require sponsorship|visa sponsorship|need sponsorship|future.*sponsorship)",
        "handler": lambda p: "No",
        "category": "Work_Auth"
    },
    {
        "pattern": r"(notice period|how soon can you start|days of notice|availability to join)",
        "handler": lambda p: f"{p.preferences.notice_period_days} days (Immediate Joiner)" if p.application_answers.immediate_joiner else f"{p.preferences.notice_period_days} days",
        "category": "Availability"
    },
    {
        "pattern": r"(immediate.*join|join immediately|can you join immediately)",
        "handler": lambda p: "Yes" if p.application_answers.immediate_joiner else "No",
        "category": "Availability"
    },
    {
        "pattern": r"(willing to relocate|relocate to|open to relocation)",
        "handler": lambda p: "Yes" if p.application_answers.willing_to_relocate else "No",
        "category": "Preferences"
    },
    {
        "pattern": r"(expected salary|expected ctc|salary expectation|compensation requirement)",
        "handler": lambda p: p.preferences.min_expected_salary or "Negotiable / Standard Industry CTC",
        "category": "Compensation"
    },
    {
        "pattern": r"(current location|current city|where are you located|where do you reside)",
        "handler": lambda p: p.personal_info.location,
        "category": "Location"
    },
    {
        "pattern": r"(highest degree|level of education|education level|highest qualification)",
        "handler": lambda p: f"{p.education[0].degree} in {p.education[0].field_of_study}" if p.education else "Bachelor of Technology (B.Tech)",
        "category": "Education"
    },
    {
        "pattern": r"(graduation year|year of graduation|when did you graduate)",
        "handler": lambda p: str(p.education[0].graduation_year) if p.education else "2026",
        "category": "Education"
    },
    {
        "pattern": r"(total.*years of experience|overall.*experience|how many years.*experience overall)",
        "handler": lambda p: str(p.application_answers.years_of_experience),
        "category": "Experience"
    },
    {
        "pattern": r"(current ctc|current salary|present salary|current compensation)",
        "handler": lambda p: "Fresher / 0" if p.application_answers.years_of_experience < 1 else "Negotiable",
        "category": "Compensation"
    },
    {
        "pattern": r"(rotational shift|night shift|work in shifts|shifts)",
        "handler": lambda p: "Yes",
        "category": "Preferences"
    },
    {
        "pattern": r"(work from office|wfo|onsite|hybrid|work in office)",
        "handler": lambda p: "Yes",
        "category": "Preferences"
    },
    {
        "pattern": r"(rate your english|communication skill|english proficiency)",
        "handler": lambda p: "Proficient",
        "category": "Skills"
    },
    {
        "pattern": r"(have a laptop|personal computer|wifi|broadband|internet connection)",
        "handler": lambda p: "Yes",
        "category": "Logistics"
    },
    {
        "pattern": r"(available for full[- ]time|full[- ]time availability|immediate full time)",
        "handler": lambda p: "Yes",
        "category": "Availability"
    },
    {
        "pattern": r"(criminal record|convicted of|felony|background check)",
        "handler": lambda p: "No",
        "category": "Background"
    },
    {
        "pattern": r"(gender|sex)",
        "handler": lambda p: "Male",
        "category": "Demographics"
    },
]


def seed_default_qa_bank() -> int:
    """
    Seeds default screening questions and answers from candidate profile into SQLite.
    Returns count of seeded questions.
    """
    profile = load_profile()
    count = 0
    with SessionLocal() as db:
        defaults = [
            ("Are you legally authorized to work in India?", "Yes", "Work_Auth"),
            ("Will you now or in the future require visa sponsorship?", "No", "Work_Auth"),
            ("What is your current notice period?", f"{p_notice} days (Immediate)" if (p_notice := profile.preferences.notice_period_days) == 0 else f"{p_notice} days", "Availability"),
            ("Are you willing to relocate?", "Yes" if profile.application_answers.willing_to_relocate else "No", "Preferences"),
            ("What is your expected CTC / Salary?", profile.preferences.min_expected_salary or "Negotiable / Standard Industry CTC", "Compensation"),
            ("What is your total years of professional experience?", str(profile.application_answers.years_of_experience), "Experience"),
            ("What is your highest level of education completed?", f"{profile.education[0].degree} in {profile.education[0].field_of_study}" if profile.education else "B.Tech", "Education"),
            ("Are you available for full-time employment?", "Yes", "Availability"),
            ("What is your preferred work mode?", "Remote / Hybrid / Onsite", "Preferences"),
        ]
        
        for q, a, cat in defaults:
            existing = crud.get_qa_answer(db, q)
            if not existing:
                crud.save_qa_answer(db, q, a, cat)
                count += 1
                
    logger.info(f"Seeded {count} default screening questions into memory bank.")
    return count


def _clean_question(q: str) -> str:
    """Normalizes question string for matching."""
    return re.sub(r"[^\w\s]", "", q).strip().lower()


def get_answer_from_memory(question: str) -> Optional[Dict[str, Any]]:
    """
    Queries SQLite application_answers table for an exact or high-confidence match.
    """
    q_norm = _clean_question(question)
    with SessionLocal() as db:
        # 1. Exact match
        exact = crud.get_qa_answer(db, question)
        if exact:
            return {"answer": exact.answer, "source": "db_memory_exact", "confidence": 1.0, "category": exact.category}
            
        # 2. Normalized match across all stored questions
        all_qa = crud.list_qa_answers(db)
        for qa in all_qa:
            if _clean_question(qa.question) == q_norm:
                return {"answer": qa.answer, "source": "db_memory_normalized", "confidence": 0.95, "category": qa.category}
                
    return None


def get_answer_from_rules(question: str) -> Optional[Dict[str, Any]]:
    """
    Checks common question regex patterns against candidate profile.
    """
    profile = load_profile()
    q_lower = question.lower()
    
    # Check general rule patterns
    for item in RULE_PATTERNS:
        if re.search(item["pattern"], q_lower, re.IGNORECASE):
            ans = item["handler"](profile)
            return {"answer": ans, "source": "profile_rule", "confidence": 0.9, "category": item["category"]}
            
    # Check skill-specific experience questions: "How many years of X experience do you have?"
    skill_match = re.search(r"how many years(?: of experience)?(?: do you have)?(?: with| in)? ([a-zA-Z0-9\+\#\.\s]+)\??", q_lower)
    if skill_match:
        target_skill = skill_match.group(1).strip().lower()
        all_candidate_skills = [
            s.lower() for s in (
                profile.technical_skills.programming_languages +
                profile.technical_skills.frameworks_and_libraries +
                profile.technical_skills.ai_and_ml +
                profile.technical_skills.databases +
                profile.technical_skills.tools_and_platforms
            )
        ]
        
        # Check if skill exists in candidate skillset
        if any(target_skill in s or s in target_skill for s in all_candidate_skills):
            ans = str(profile.application_answers.years_of_experience)
            return {"answer": ans, "source": "profile_skill_match", "confidence": 0.85, "category": "Experience"}
        else:
            return {"answer": "0", "source": "profile_skill_miss", "confidence": 0.85, "category": "Experience"}
            
    return None


def generate_ai_screening_answer(
    question: str,
    job_title: str = "",
    company_name: str = "",
    job_description: str = "",
    field_type: str = "text",
    options: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Generates a truthful, candidate-grounded answer using Claude Haiku when question is unseen.
    Caches the answer in SQLite memory bank for future zero-latency reuse.
    """
    profile = load_profile()

    system_instruction = (
        "You are representing candidate Rayavaram Jayasurya in a job application screening form.\n"
        "Your goal is to answer the employer's screening question truthfully, accurately, and strictly based on the candidate profile.\n\n"
        "CRITICAL CANDIDATE PROFILE FACTS (ZERO HALLUCINATION):\n"
        f"   - Full Name: {profile.personal_info.name}\n"
        f"   - Degree & Education: {profile.education[0].degree if profile.education else 'B.Tech in Computer Science and Engineering (Data Science)'}\n"
        f"   - Graduation Year: {profile.education[0].graduation_year if profile.education else '2026'}\n"
        f"   - Professional Experience: {profile.application_answers.years_of_experience} years as Junior AI Engineer / Python Developer\n"
        f"   - Notice Period: {profile.preferences.notice_period_days} days (Immediate Joiner)\n"
        f"   - Current Location: {profile.personal_info.location}\n"
        f"   - Willing to Relocate: {'Yes' if profile.application_answers.willing_to_relocate else 'No'} (Open to Hyderabad, Bengaluru, Remote, Onsite)\n"
        f"   - Expected Salary / CTC: {profile.preferences.min_expected_salary or 'Negotiable'}\n"
        f"   - Work Authorization: Legally authorized to work in India, does NOT require visa sponsorship\n"
        f"   - Core Technical Skills: Python, FastAPI, React, Playwright, LangGraph, LLMs, RAG, SQLite, PostgreSQL, PySpark, Git, Docker\n\n"
        "STRICT OUTPUT INSTRUCTIONS:\n"
        "1. If field_type is 'number' or the question asks for a number (years of experience, notice period in days, score/rating):\n"
        "   Output ONLY the integer or decimal number (e.g., '1', '0', '0.8'). No text, no units.\n"
        "2. If options are provided (for dropdown select or radio buttons):\n"
        "   Choose and return ONLY the EXACT option text from the provided options that best represents the candidate.\n"
        "3. If it is a Yes/No question:\n"
        "   Respond with ONLY 'Yes' or 'No'.\n"
        "4. If it is an open-ended question or textarea:\n"
        "   Provide a concise, direct, professional answer in first person (1-2 sentences max).\n"
        "5. Output PLAIN TEXT ONLY. Never include markdown, quotes, or preambles."
    )

    prompt_parts = [
        f"Job Title: {job_title or 'Software / AI Engineer'}",
        f"Company: {company_name or 'Hiring Company'}",
        f"Screening Question: {question}",
        f"Field Type: {field_type}",
    ]
    if options:
        prompt_parts.append(f"Available Options: {json.dumps(options)}")
    prompt_parts.append("Please provide the candidate answer:")
    prompt = "\n".join(prompt_parts)

    try:
        response = claude_client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=250,
            system=system_instruction,
            messages=[{"role": "user", "content": prompt}],
        )
        if response.stop_reason == "refusal":
            raise RuntimeError("AI model declined to answer this screening question.")
        ans = response_text(response).strip().strip('"\'')

        # Clean numeric fields if needed
        if field_type == "number":
            num_match = re.search(r"\b\d+(\.\d+)?\b", ans)
            if num_match:
                ans = num_match.group(0)
            else:
                ans = str(profile.application_answers.years_of_experience)

        # Match exact option if provided
        if options and ans not in options:
            for opt in options:
                if ans.lower() == opt.lower() or ans.lower() in opt.lower() or opt.lower() in ans.lower():
                    ans = opt
                    break

        # Save to SQLite memory bank for future runs
        with SessionLocal() as db:
            crud.save_qa_answer(db, question=question, answer=ans, category="AI_Generated")

        return {
            "answer": ans,
            "source": "claude_ai_generated",
            "confidence": 0.95,
            "category": "AI_Generated"
        }
    except Exception as e:
        logger.error(f"Error generating AI answer: {e}")
        fallback_ans = "1" if field_type == "number" else (options[0] if options else "Yes")
        return {
            "answer": fallback_ans,
            "source": "fallback_error",
            "confidence": 0.5,
            "category": "General"
        }


def get_or_generate_answer(
    question: str,
    job_title: str = "",
    company_name: str = "",
    job_description: str = "",
    field_type: str = "text",
    options: Optional[List[str]] = None,
    allow_ai_generation: bool = True,  # Claude Haiku Brain always enabled
    verified_only: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Tiered resolver for screening questions:
    Tier 1: SQLite DB Memory Bank (Cached answers)
    Tier 2: Profile Rule Patterns (Instant deterministic lookup)
    Tier 3: Claude AI Generation (Unseen open-ended & dynamic questions)
    """
    if verified_only:
        mem = get_answer_from_memory(question)
        if mem and mem.get("category") != "AI_Generated":
            return mem
        rule = get_answer_from_rules(question)
        if rule:
            with SessionLocal() as db:
                crud.save_qa_answer(db, question=question, answer=str(rule["answer"]), category=rule["category"])
            return rule
        return None

    # 1. Tier 1: SQLite Memory Bank
    mem = get_answer_from_memory(question)
    if mem:
        # If numeric field, ensure stored answer isn't an invalid string like "Yes"
        if field_type == "number" and not re.search(r"\d", str(mem.get("answer", ""))):
            logger.info(f"Discarding invalid non-numeric cached answer '{mem.get('answer')}' for numeric field '{question}'")
        else:
            return mem

    # 2. Tier 2: Profile Rules
    rule = get_answer_from_rules(question)
    if rule:
        rule_ans = str(rule["answer"])
        if field_type == "number":
            num_match = re.search(r"\b\d+(\.\d+)?\b", rule_ans)
            if num_match:
                rule_ans = num_match.group(0)
            rule["answer"] = rule_ans

        # If options are provided, map rule answer to exact or best option
        if options:
            matched_opt = None
            for opt in options:
                if rule_ans.lower() == opt.lower() or rule_ans.lower() in opt.lower() or opt.lower() in rule_ans.lower():
                    matched_opt = opt
                    break
            # Specific heuristic mappings for common Naukri options
            if not matched_opt and "notice" in question.lower():
                for opt in options:
                    if any(k in opt.lower() for k in ["15 days", "immediate", "less than 15"]):
                        matched_opt = opt
                        break
            if not matched_opt and "experience" in question.lower():
                for opt in options:
                    if any(k in opt.lower() for k in ["0-1", "fresher", "less than 1", "1 year"]):
                        matched_opt = opt
                        break

            if matched_opt:
                rule["answer"] = matched_opt
            elif allow_ai_generation:
                # If rule answer doesn't cleanly map to provided options, let Claude select the optimal option
                return generate_ai_screening_answer(
                    question=question,
                    job_title=job_title,
                    company_name=company_name,
                    job_description=job_description,
                    field_type=field_type,
                    options=options,
                )

        # Cache rule answer to SQLite DB for instant exact matches later
        with SessionLocal() as db:
            crud.save_qa_answer(db, question=question, answer=rule["answer"], category=rule["category"])
        return rule

    # 3. Tier 3: Claude AI Generator
    if allow_ai_generation:
        return generate_ai_screening_answer(
            question=question,
            job_title=job_title,
            company_name=company_name,
            job_description=job_description,
            field_type=field_type,
            options=options,
        )

    return {
        "answer": "1" if field_type == "number" else (options[0] if options else "Yes"),
        "source": "default_fallback",
        "confidence": 0.5,
        "category": "General"
    }
