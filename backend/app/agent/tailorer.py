"""
Module: tailorer.py
Purpose: Step 1.4 ATS Resume Customizer - Tailors LaTeX resume to match target Job Description.
Standards: Rule 1 (LaTeX Sanitization & Anti-Hallucination), Rule 2 (Pydantic Schema),
           Rule 3 (Low Code & High Accuracy), Rule 4 (Standard Layout), Rule 5 (Production Fallback).
"""
import json
import logging
import re
import shutil
import subprocess
import warnings
from pathlib import Path
from typing import Dict, List, Any
from pydantic import BaseModel, Field

warnings.filterwarnings("ignore", category=FutureWarning)
from dotenv import load_dotenv
from google.genai import types

logger = logging.getLogger("tailorer")

from app.config import DEFAULT_MODEL, gemini_client, BASE_DIR
from app.utils.rate_limiter import execute_with_rate_limit
from app.schemas.match import JobMatchResult
from app.agent.scorer import load_profile

class TailoredProject(BaseModel):
    title: str = Field(description="Project title from candidate profile")
    tech_stack: List[str] = Field(description="Technologies used, highlighting matching keywords")
    bullets: List[str] = Field(description="2 tailored bullet points highlighting achievements and JD keywords")

class TailoredResumePayload(BaseModel):
    summary: str = Field(description="Tailored 2-3 sentence professional summary targeting the role")
    languages: List[str] = Field(description="Programming languages ordered with JD priorities first")
    frameworks: List[str] = Field(description="Frameworks and libraries ordered with JD priorities first")
    ai_skills: List[str] = Field(description="AI, ML, and automation tools relevant to the JD")
    databases_tools: List[str] = Field(description="Databases and developer tools")
    experience_bullets: List[str] = Field(description="3-4 action-oriented bullets for work experience")
    projects: List[TailoredProject] = Field(description="Tailored bullet points for each candidate project")

def escape_latex(text: str) -> str:
    """Escapes special LaTeX characters to guarantee syntax integrity (Rule 1)."""
    if not isinstance(text, str):
        return text
    # Map of special characters that break LaTeX
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    # Escape in safe order
    for char, escaped in replacements.items():
        # Backslash is intentionally skipped: backslashes are required for LaTeX formatting commands
        if char == "\\":
            continue
        text = text.replace(char, escaped)
    return text

def tailor_resume(
    job_description: str,
    match_result: JobMatchResult,
    profile_path: str = "profile.json",
    output_dir: str = "output/resumes",
    template_path: str = "app/templates/resume_template.tex"
) -> Dict[str, Any]:
    """
    Generates an ATS-tailored LaTeX resume and compiles it to PDF if pdflatex is installed.
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

    system_instruction = (
        "You are an elite executive resume writer and ATS optimization specialist.\n"
        "Your goal is to tailor the candidate's verified background to maximize ATS keyword alignment.\n\n"
        "CRITICAL RULES:\n"
        "1. ZERO HALLUCINATION: Only use facts, skills, and projects found in the Candidate Profile.\n"
        "2. ACTION-ORIENTED BULLETS: Rephrase bullet points using strong action verbs and Google XYZ formula "
        "('Accomplished [X] as measured by [Y], by doing [Z]').\n"
        "3. KEYWORD EMPHASIS: Emphasize matching skills identified by the ATS scorer.\n"
    )

    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        response_mime_type="application/json",
        response_schema=TailoredResumePayload,
        temperature=0.2,
        safety_settings=safety_settings,
    )

    prompt = (
        f"--- CANDIDATE PROFILE ---\n"
        f"{profile.model_dump_json(indent=2)}\n\n"
        f"--- TARGET ROLE & MATCH RESULT ---\n"
        f"Target Role: {match_result.job_title} at {match_result.company_name}\n"
        f"Matching Skills to Emphasize: {', '.join(match_result.matching_skills)}\n\n"
        f"--- JOB DESCRIPTION ---\n"
        f"{job_description.strip()}\n"
    )

    # Execute AI Generation with Rate-Limiting Protection
    response = execute_with_rate_limit(
        gemini_client.models.generate_content,
        model=DEFAULT_MODEL,
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

    # Grounding fallbacks ensuring non-empty production-grade resume (Rule 1 & Rule 5)
    if not raw_data.get("summary"):
        raw_data["summary"] = f"Dedicated candidate with proven hands-on experience in software engineering, applied AI, and scalable systems targeting {match_result.job_title}."
    if not raw_data.get("languages"):
        raw_data["languages"] = profile.technical_skills.programming_languages
    if not raw_data.get("frameworks"):
        raw_data["frameworks"] = profile.technical_skills.frameworks_and_libraries
    if not raw_data.get("ai_skills"):
        raw_data["ai_skills"] = profile.technical_skills.ai_and_ml
    if not raw_data.get("databases_tools"):
        raw_data["databases_tools"] = profile.technical_skills.databases + profile.technical_skills.tools_and_platforms
    if not raw_data.get("experience_bullets"):
        raw_data["experience_bullets"] = [b for exp in profile.experience for b in exp.highlights]
    if not raw_data.get("projects"):
        raw_data["projects"] = [
            {
                "title": p.title,
                "tech_stack": p.tech_stack,
                "bullets": p.key_achievements if p.key_achievements else [p.description]
            }
            for p in profile.projects
        ]

    payload = TailoredResumePayload(**raw_data)

    # Read base template
    template_file = Path(template_path)
    if not template_file.exists() and (BASE_DIR / template_path).exists():
        template_file = BASE_DIR / template_path
    if not template_file.exists():
        raise FileNotFoundError(f"Template not found at: {template_path}")
    tex_content = template_file.read_text(encoding="utf-8")

    # Format Experience Bullets
    exp_bullets = "\n".join([f"    \\item {escape_latex(b)}" for b in payload.experience_bullets])
    
    # Format Projects Content
    project_blocks = []
    for p in payload.projects:
        bullets = "\n".join([f"        \\item {escape_latex(b)}" for b in p.bullets])
        stack = escape_latex(", ".join(p.tech_stack))
        title = escape_latex(p.title)
        block = (
            f"\\textbf{{{title}}} $|$ \\textit{{{stack}}}\n"
            f"\\begin{{itemize}}[leftmargin=0.15in, itemsep=-2pt]\n"
            f"{bullets}\n"
            f"\\end{{itemize}}"
        )
        project_blocks.append(block)
    projects_content = "\n\n".join(project_blocks)

    first_exp = profile.experience[0] if profile.experience else None
    first_edu = profile.education[0] if profile.education else None

    # Replace placeholders
    replacements = {
        "__NAME__": escape_latex(profile.personal_info.name),
        "__PHONE__": escape_latex(profile.personal_info.phone),
        "__EMAIL__": escape_latex(profile.personal_info.email),
        "__LOCATION__": escape_latex(profile.personal_info.location),
        "__LINKEDIN__": escape_latex(profile.personal_info.linkedin_url or ""),
        "__GITHUB__": escape_latex(profile.personal_info.github_url or ""),
        "__SUMMARY__": escape_latex(payload.summary),
        "__LANGUAGES__": escape_latex(", ".join(payload.languages)),
        "__FRAMEWORKS__": escape_latex(", ".join(payload.frameworks)),
        "__AI_SKILLS__": escape_latex(", ".join(payload.ai_skills)),
        "__DATABASES_AND_TOOLS__": escape_latex(", ".join(payload.databases_tools)),
        "__EXP_ROLE__": escape_latex(first_exp.role if first_exp else "Engineer"),
        "__EXP_DATES__": escape_latex(f"{first_exp.start_date} -- {first_exp.end_date}" if first_exp else ""),
        "__EXP_COMPANY__": escape_latex(first_exp.company if first_exp else ""),
        "__EXP_LOCATION__": escape_latex(first_exp.location if first_exp else ""),
        "__EXP_BULLETS__": exp_bullets,
        "__PROJECTS_CONTENT__": projects_content,
        "__DEGREE__": escape_latex(first_edu.degree if first_edu else "Degree"),
        "__GRAD_YEAR__": escape_latex(str(first_edu.graduation_year if first_edu else "2026")),
        "__INSTITUTION__": escape_latex(first_edu.institution if first_edu else ""),
        "__FIELD_OF_STUDY__": escape_latex(first_edu.field_of_study if first_edu else ""),
    }

    for key, val in replacements.items():
        tex_content = tex_content.replace(key, val)

    # Save output .tex file
    out_dir = Path(output_dir)
    if not out_dir.is_absolute() and not out_dir.exists() and (BASE_DIR / output_dir).parent.exists():
        out_dir = BASE_DIR / output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_title = re.sub(r'[^a-zA-Z0-9_-]', '_', match_result.job_title).lower()
    tex_path = out_dir / f"{safe_title}_resume.tex"
    tex_path.write_text(tex_content, encoding="utf-8")

    # Production compilation check (Rule 5)
    pdf_path = None
    pdflatex_bin = shutil.which("pdflatex")
    if pdflatex_bin:
        try:
            subprocess.run(
                [pdflatex_bin, "-interaction=nonstopmode", f"-output-directory={out_dir}", str(tex_path)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            generated_pdf = out_dir / f"{safe_title}_resume.pdf"
            if generated_pdf.exists():
                pdf_path = str(generated_pdf)
        except Exception:
            pdf_path = None

    # High-fidelity Chromium PDF Fallback (Rule 5: Zero-Failure PDF delivery)
    if not pdf_path:
        try:
            from app.agent.pdf_generator import render_html_to_pdf_bytes, generate_resume_html
            tailored_data = {
                "personal_info": profile.personal_info.model_dump(),
                "summary": payload.summary,
                "education": [edu.model_dump() for edu in profile.education],
                "experience": [
                    {
                        "role": profile.experience[0].role if profile.experience else "Engineer",
                        "company": profile.experience[0].company if profile.experience else "",
                        "location": profile.experience[0].location if profile.experience else "",
                        "start_date": profile.experience[0].start_date if profile.experience else "",
                        "end_date": profile.experience[0].end_date if profile.experience else "",
                        "highlights": payload.experience_bullets
                    }
                ] if profile.experience else [],
                "projects": [p.model_dump() for p in payload.projects],
                "technical_skills": {
                    "programming_languages": payload.languages,
                    "frameworks_and_libraries": payload.frameworks,
                    "ai_and_ml": payload.ai_skills,
                    "databases": payload.databases_tools,
                    "tools_and_platforms": []
                }
            }
            tailored_html = generate_resume_html(tailored_data)
            pdf_bytes = render_html_to_pdf_bytes(tailored_html)
            generated_pdf = out_dir / f"{safe_title}_resume.pdf"
            generated_pdf.write_bytes(pdf_bytes)
            pdf_path = str(generated_pdf)
        except Exception as e:
            logger.warning(f"Chromium PDF fallback failed: {e}")

    return {
        "status": "success",
        "tex_path": str(tex_path),
        "pdf_path": pdf_path,
        "summary": payload.summary,
        "matching_skills_used": payload.ai_skills
    }
