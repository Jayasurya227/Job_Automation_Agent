"""
Module: scorer.py
Purpose: Step 1.3 AI Brain - Analyzes, scores, and classifies Job Descriptions against Candidate Profile using Claude.
Standards: Rule 1 (Anti-Hallucination Guardrails), Rule 2 (Pydantic Schema Enforcement),
           Rule 3 (Concise & Modular), Rule 4 (Structured Directory), Rule 5 (Production Standard).
"""
import json
from pathlib import Path

from app.config import DEFAULT_MODEL, claude_client, BASE_DIR
from app.agent.llm import response_text, parse_json_object
from app.utils.rate_limiter import execute_with_rate_limit
from app.schemas.profile import CandidateProfile
from app.schemas.match import JobMatchResult

def load_profile(profile_path: str = "profile.json") -> CandidateProfile:
    """Dynamically loads and validates candidate profile from disk."""
    target = Path(profile_path)
    if not target.exists() and (BASE_DIR / profile_path).exists():
        target = BASE_DIR / profile_path
    if not target.exists():
        raise FileNotFoundError(f"Profile not found at: {profile_path}")
    with open(target, "r", encoding="utf-8") as f:
        data = json.load(f)
    return CandidateProfile(**data)

def analyze_and_score_job(
    job_description: str,
    profile_path: str = "profile.json",
    model_name: str = DEFAULT_MODEL,
    title: str = "",
    company: str = "",
    portal: str = "",
    job_url: str = "",
) -> JobMatchResult:
    """
    Evaluates a raw Job Description against the Candidate Profile using Claude AI Brain.
    Enforces pure JSON output matching JobMatchResult Pydantic schema.
    Also intelligently classifies whether applying is native 1-Click vs External company portal.
    Grounds experience strictly in the user's Settings tab (Single Source of Truth),
    never guessing or penalizing based on college graduation year or resume dates.
    """
    # 1. Load dynamic candidate profile & experience level from Settings (Single Source of Truth)
    profile = load_profile(profile_path)
    exp_level = getattr(profile.preferences, "experience_level", "0-1") or "0-1"
    exp_labels = {
        "0-1": "0-1 Years (Fresher / Entry Level)",
        "1-2": "1-2 Years (Early Career)",
        "2-4": "2-4 Years (Associate / Junior)",
        "all": "Any Experience Level"
    }
    exp_label = exp_labels.get(exp_level, exp_level)

    # 2. Strict Grounded System Prompt (Rule 1: Anti-Hallucination)
    system_instruction = (
        "You are an objective, senior technical recruiter and ATS evaluation engine.\n"
        "Your task is to accurately score a Job Description against a verified Candidate Profile "
        "and classify the application method.\n\n"
        "CRITICAL GROUNDING RULES:\n"
        "1. STRICT TRUTH: You must ONLY evaluate skills and achievements explicitly stated in the Candidate Profile.\n"
        "2. NO FABRICATION: Never invent, extrapolate, or assume skills the candidate has not listed.\n"
        "3. EXPERIENCE GROUNDING (STRICTLY FROM SETTINGS, ZERO RESUME DATE GUESSWORK):\n"
        f"   - The candidate's target experience level is explicitly set in Settings as: '{exp_label}'.\n"
        "   - DO NOT infer or penalize experience based on college graduation dates (e.g. 2026) or resume dates, as candidates often work, intern, or build production systems during college.\n"
        f"   - If target experience is 'Any Experience Level', do NOT penalize for years of experience; evaluate purely on technical skill match, tools, and project relevance.\n"
        f"   - If target experience is '0-1 Years' or '1-2 Years', but the Job Description explicitly requires 3+ years of senior experience or team leadership, reduce the match score (typically between 55% and 69%) to reflect the experience gap, keeping it in Review and preventing premature auto-applying (which requires >= 80%).\n"
        "   - If the required experience matches or candidate has the core tech stack, score 70-100% based on relevance.\n"
        "4. ACCURATE SCORING BRACKETS:\n"
        "   - Score 80-100: Candidate has all primary required skills and relevant projects (Auto-Apply candidate).\n"
        "   - Score 70-79: Strong core skills and projects, but minor tools or experience variance (Review queue).\n"
        "   - Score 50-69: Moderate skill overlap or higher experience requirement than candidate's target level (Review queue).\n"
        "   - Score 0-49: Candidate lacks primary core requirements or foundational programming skills.\n"
        "5. RECOMMENDATION LOGIC:\n"
        "   - 'Apply' if match_score >= 70\n"
        "   - 'Review' if match_score is between 50 and 69\n"
        "   - 'Skip' if match_score < 50\n"
        "6. DOMAIN & TECHNICAL COMPETENCY PRIORITY (ZERO PENALTY FOR GENERIC SOFT SKILLS):\n"
        "   - The candidate's verified universal soft skills (e.g. Fluent English Communication, Written & Verbal Communication, Problem Solving, Team Collaboration, Adaptability) are verified and present in their profile.\n"
        "   - For Technical/Engineering roles (e.g. AI Engineer, Python Developer, Full Stack, SDE), evaluate the ATS match score based primarily on Core Technical Competencies: programming languages, frameworks, system design, databases, APIs, and relevant technical projects.\n"
        "   - DO NOT penalize the ATS score or deduct points if the Job Description mentions generic soft skills, behavioral buzzwords, or HR boilerplate (such as 'ownership', 'leadership', 'content writing', 'presentation skills', 'active listening', 'fast learner', 'dynamic personality') that are not explicitly stated on the candidate's resume.\n"
        "   - In 'missing_skills', NEVER list generic soft skills or HR boilerplate words (e.g., do NOT list 'ownership', 'leadership', 'good communication' as missing skills). 'missing_skills' must ONLY list genuine missing technical tools, programming languages, or domain-critical technical competencies required by the job.\n"
        "7. APPLICATION METHOD CLASSIFICATION (1-Click vs External Company Portal):\n"
        "   - Default to '1-Click' for jobs natively hosted on Naukri.com or Indeed.\n"
        "   - DO NOT classify as 'External' simply because the job description text mentions an email address, phone number, or recruiter boilerplate like 'send CV to ...'. Naukri postings have native 1-Click apply regardless of recruiter text.\n"
        "   - ONLY classify as 'External' if the job URL explicitly points to an external corporate ATS domain (e.g. workday.com, greenhouse.io, lever.co, myworkdayjobs.com) or the page explicitly displays 'Apply on company site'.\n"
        "   - In 'apply_type_reasoning', write a 1-sentence rationale explaining why you classified it as 1-Click or External.\n\n"
        "Respond with ONLY a JSON object matching this JSON schema, no other text:\n"
        f"{json.dumps(JobMatchResult.model_json_schema())}\n"
    )

    # 3. Construct prompt payload
    soft_skills_list = getattr(profile.technical_skills, "soft_skills", []) or []
    soft_skills_str = ", ".join(soft_skills_list) if soft_skills_list else "Fluent English Communication, Written & Verbal Communication, Problem Solving, Team Collaboration"

    meta_parts = []
    if title:
        meta_parts.append(f"Job Title: {title}")
    if company:
        meta_parts.append(f"Company: {company}")
    if portal:
        meta_parts.append(f"Job Portal: {portal}")
    if job_url:
        meta_parts.append(f"Listing URL: {job_url}")
    meta_block = "\n".join(meta_parts) if meta_parts else "Not specified"

    prompt = (
        f"--- TARGET JOB METADATA ---\n"
        f"{meta_block}\n\n"
        f"--- CANDIDATE TARGET EXPERIENCE (FROM SETTINGS) ---\n"
        f"Candidate Experience Level: {exp_label}\n\n"
        f"--- CANDIDATE VERIFIED SOFT SKILLS & STRENGTHS ---\n"
        f"{soft_skills_str}\n\n"
        f"--- CANDIDATE PROFILE ---\n"
        f"{profile.model_dump_json(indent=2)}\n\n"
        f"--- TARGET JOB DESCRIPTION ---\n"
        f"{job_description.strip()}\n"
    )

    # 4. Execute AI call with rate-limit protection
    response = execute_with_rate_limit(
        claude_client.messages.create,
        model=model_name,
        max_tokens=4000,
        system=system_instruction,
        messages=[{"role": "user", "content": prompt}],
    )

    # 5. Guardrails (Rule 1 & Rule 5)
    if response.stop_reason == "refusal":
        raise RuntimeError("AI model refused to score this job description.")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("AI response was cut off before completing the score.")

    # 6. Parse into Pydantic schema (Rule 2: Type validation)
    result_data = parse_json_object(response_text(response))
    return JobMatchResult(**result_data)
