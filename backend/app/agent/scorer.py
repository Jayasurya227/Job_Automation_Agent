"""
Module: scorer.py
Purpose: Step 1.3 AI Brain - Analyzes, scores, and classifies Job Descriptions against Candidate Profile using Claude.
Standards: Rule 1 (Anti-Hallucination Guardrails), Rule 2 (Pydantic Schema Enforcement),
           Rule 3 (Concise & Modular), Rule 4 (Structured Directory), Rule 5 (Production Standard).
"""
import json
import re
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

def _normalize_tech_word(word: str) -> str:
    w = word.lower().strip()
    if w.endswith(".js"):
        w = w[:-3]
    elif w.endswith("js") and len(w) > 4:
        w = w[:-2]
    return w

def _extract_tech_tokens(phrase: str) -> set[str]:
    raw_tokens = re.findall(r'[a-zA-Z0-9+#.]+', phrase.lower())
    tokens = set()
    for tok in raw_tokens:
        tok_clean = tok.strip(".,;:!?")
        if tok_clean:
            tokens.add(tok_clean)
            norm = _normalize_tech_word(tok_clean)
            if norm:
                tokens.add(norm)
    return tokens

TECH_STOPWORDS = {
    "web", "data", "software", "system", "systems", "cloud", "developer",
    "development", "engineer", "engineering", "technologies", "technology",
    "programming", "scripting", "framework", "frameworks", "library",
    "libraries", "tools", "tool", "queries", "query", "database",
    "databases", "service", "services", "solution", "solutions", "app", "apps",
    "application", "applications", "architecture", "platform", "platforms"
}

def sanitize_skills_report(result_data: dict) -> dict:
    """
    Step 2 Universal Skills Sanitizer:
    1. Deduplicates skills within matching and missing lists.
    2. Strips out cross-contamination: if a skill/concept is credited in matching_skills,
       ensures it never appears in missing_skills.
    3. Scrubs generic HR buzzwords (e.g. communication, ownership, teamwork) from missing_skills
       so missing_skills strictly reflects genuine core domain/technical competencies.
    4. Operates universally across any profile (Frontend, Backend, AI, Data, DevOps, Non-IT).
    """
    if not isinstance(result_data, dict):
        return result_data

    raw_matching = result_data.get("matching_skills") or []
    raw_missing = result_data.get("missing_skills") or []

    # 1. Clean & normalize matching skills
    cleaned_matching = []
    seen_matching_lower = set()
    matching_token_map = []  # list of (full_phrase, set_of_tokens)

    for s in raw_matching:
        if not s or not isinstance(s, str):
            continue
        clean_s = s.strip().strip("-•* \t\r\n")
        if not clean_s:
            continue
        lower_s = clean_s.lower()
        if lower_s not in seen_matching_lower:
            seen_matching_lower.add(lower_s)
            cleaned_matching.append(clean_s)
            matching_token_map.append((lower_s, _extract_tech_tokens(clean_s)))

    # 2. Universal non-technical HR buzzwords that should never be in missing_skills
    GENERIC_BUZZWORDS = {
        "communication", "written communication", "verbal communication",
        "oral communication", "presentation skills", "team player",
        "teamwork", "team collaboration", "interpersonal skills",
        "problem solving", "analytical skills", "critical thinking",
        "ownership", "self starter", "self-starter", "fast learner",
        "quick learner", "active listener", "dynamic personality",
        "multitasking", "work ethic", "adaptability", "flexibility",
        "time management", "attention to detail", "positive attitude",
        "enthusiastic", "leadership", "mentorship", "hard working", "hard-working",
        "creative thinking", "good listener", "strong work ethic", "self-motivated"
    }

    # 3. Clean & resolve conflicts for missing skills
    cleaned_missing = []
    seen_missing_lower = set()

    for s in raw_missing:
        if not s or not isinstance(s, str):
            continue
        clean_s = s.strip().strip("-•* \t\r\n")
        if not clean_s:
            continue
        lower_s = clean_s.lower()

        # A: Drop if matches any generic HR buzzword
        if lower_s in GENERIC_BUZZWORDS:
            continue
        # Also drop if it's a short phrase consisting predominantly of buzzwords (e.g. "strong communication")
        if any(b == lower_s or lower_s.startswith(f"{b} ") or lower_s.endswith(f" {b}") or f" {b} " in lower_s for b in ["communication", "team player", "problem solving", "ownership"]):
            continue

        # B: Drop if duplicate within missing_skills
        if lower_s in seen_missing_lower:
            continue

        # C: Conflict Resolution: Drop if already credited in matching_skills
        missing_tokens = _extract_tech_tokens(clean_s)
        is_already_matched = False

        for m_phrase, m_tokens in matching_token_map:
            # Direct string equality or containment
            if lower_s == m_phrase:
                is_already_matched = True
                break
            # Java vs JavaScript distinction guardrail
            if (lower_s == "java" and "javascript" in m_phrase) or (m_phrase == "java" and "javascript" in lower_s):
                continue
            # Meaningful technical token overlap (e.g. SQL in SQL Queries, React in React.js)
            shared_tokens = (missing_tokens & m_tokens) - TECH_STOPWORDS
            if shared_tokens:
                is_already_matched = True
                break

        if not is_already_matched:
            seen_missing_lower.add(lower_s)
            cleaned_missing.append(clean_s)

    result_data["matching_skills"] = cleaned_matching
    result_data["missing_skills"] = cleaned_missing
    return result_data

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
        "You are an objective, senior technical recruiter and universal hybrid ATS evaluation engine.\n"
        "Your task is to accurately score a Job Description against a verified Candidate Profile "
        "using dual-layer evaluation (Keyword Precision + Semantic Conceptual Reasoning) and classify the application method.\n\n"
        "CRITICAL UNIVERSAL HYBRID EVALUATION RULES:\n"
        "1. DUAL-LAYER EVALUATION (EXACT KEYWORD MATCH + DYNAMIC SEMANTIC UNDERSTANDING):\n"
        "   - Layer 1 (Keyword Precision): Award direct, grounded match points when technologies, tools, or domain terms match verbatim between the Job Description and Candidate Profile.\n"
        "   - Layer 2 (Universal Semantic Reasoning): Use your deep pre-trained world and domain intelligence across all fields (software, AI/ML, frontend, backend, data, cloud, operations, non-IT). Understand conceptual, paradigm, and framework equivalence dynamically with zero rigid word-for-word constraints. For example, possessing modern production frameworks, real-world projects, or architectural implementations inherently demonstrates mastery of the corresponding paradigm. A candidate with a broader technical competency possesses its foundational subsets. Never penalize a candidate simply because they used specific framework or tool terminology instead of the job description's generic phrasing.\n"
        "   - Anti-Hallucination Guardrail: While recognizing genuine technical and conceptual equivalence, never fabricate skills or credit completely unrelated domains (e.g., do not match Java Enterprise stack to Python, or C++ firmware to Web frontend).\n"
        "2. UNIVERSAL 80/20 CORE FUNCTION PRIORITY (ZERO PENALTY FOR SECONDARY WISHLISTS):\n"
        "   - In every job opening across any discipline, identify the primary day-to-day functional responsibility of the role.\n"
        "   - If the candidate demonstrates strong competence in the core day-to-day requirements and relevant project experience, award a baseline match score of 78% to 92%.\n"
        "   - DO NOT heavily slash match scores for peripheral, secondary tooling wishlists or infrastructure boilerplate (such as container orchestration, secondary cloud platforms, CI/CD pipelines, or niche utility libraries) that candidates routinely learn on the job within 1-2 weeks.\n"
        "   - For Junior / Fresher / Early Career roles (0-2 years), treat extensive secondary tooling laundry lists as optional recruiter wishlists, not disqualifying barriers.\n"
        "3. ACCURATE 'MATCHING_SKILLS' AND 'MISSING_SKILLS' HYGIENE:\n"
        "   - If a required concept is semantically demonstrated by the candidate's existing frameworks or projects, credit that concept in 'matching_skills', NEVER in 'missing_skills'.\n"
        "   - 'missing_skills' must strictly contain genuine, critical core competencies that the candidate truly lacks and that would prevent performing the primary job function.\n"
        "   - Never list secondary soft skills, HR buzzwords ('ownership', 'leadership', 'fast-paced', 'dynamic personality'), or peripheral wishlist utilities in 'missing_skills'.\n"
        "4. EXPERIENCE GROUNDING (STRICTLY FROM SETTINGS, ZERO RESUME DATE GUESSWORK):\n"
        f"   - The candidate's target experience level is explicitly set in Settings as: '{exp_label}'.\n"
        "   - DO NOT infer or penalize experience based on college graduation dates (e.g. 2026) or resume dates, as candidates often work, intern, or build production systems during college.\n"
        f"   - If target experience is 'Any Experience Level', do NOT penalize for years of experience; evaluate purely on technical skill match, tools, and project relevance.\n"
        f"   - If target experience is '0-1 Years' or '1-2 Years', but the Job Description explicitly requires 3+ years of senior experience or team leadership, reduce the match score (typically between 55% and 69%) to reflect the experience gap, keeping it in Review and preventing premature auto-applying (which requires >= 80%).\n"
        "   - If the required experience matches or candidate has the core tech stack, score 75-100% based on relevance.\n"
        "5. ACCURATE SCORING BRACKETS:\n"
        "   - Score 80-100: Candidate has primary required skills and relevant projects (Auto-Apply candidate).\n"
        "   - Score 70-79: Strong core skills and projects, but minor tools or experience variance (Review queue / Reserve pool).\n"
        "   - Score 50-69: Moderate skill overlap or higher experience requirement than candidate's target level (Review queue).\n"
        "   - Score 0-49: Candidate lacks primary core requirements or foundational programming skills (Discard).\n"
        "6. RECOMMENDATION LOGIC:\n"
        "   - 'Apply' if match_score >= 70\n"
        "   - 'Review' if match_score is between 50 and 69\n"
        "   - 'Skip' if match_score < 50\n"
        "7. DOMAIN & TECHNICAL COMPETENCY PRIORITY (ZERO PENALTY FOR GENERIC SOFT SKILLS):\n"
        "   - The candidate's verified universal soft skills (e.g. Fluent English Communication, Written & Verbal Communication, Problem Solving, Team Collaboration, Adaptability) are verified and present in their profile.\n"
        "   - For Technical/Engineering roles (e.g. AI Engineer, Python Developer, Full Stack, SDE), evaluate the ATS match score based primarily on Core Technical Competencies: programming languages, frameworks, system design, databases, APIs, and relevant technical projects.\n"
        "   - DO NOT penalize the ATS score or deduct points if the Job Description mentions generic soft skills or behavioral buzzwords.\n"
        "8. APPLICATION METHOD CLASSIFICATION (1-Click vs External Company Portal):\n"
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

    # 6. Parse into Pydantic schema (Rule 2: Type validation & Step 2 Sanitization)
    result_data = parse_json_object(response_text(response))
    sanitized_data = sanitize_skills_report(result_data)
    return JobMatchResult(**sanitized_data)
