"""
Module: pdf_generator.py
Purpose: Compiles Candidate Profiles and Tailored Resumes into ATS-standard vector PDFs.
Style: Based on the classic Jake Ryan LaTeX resume format (Charter/Georgia serif, uppercase rules, right-aligned dates).
Engine: Playwright Headless Chromium (eliminates dependency on heavy external LaTeX installations).
"""
import html
import logging
from typing import Dict, Any
from playwright.sync_api import sync_playwright

from app.config import OUTPUT_DIR

logger = logging.getLogger("pdf_generator")


def _esc(val: Any) -> str:
    """Escapes HTML characters safely."""
    if val is None:
        return ""
    return html.escape(str(val))


def generate_resume_html(profile_data: Dict[str, Any], title_suffix: str = "") -> str:
    """
    Renders candidate profile dictionary into HTML matching the Jake Ryan LaTeX template.
    """
    personal = profile_data.get("personal_info", {})
    skills = profile_data.get("technical_skills", {})
    experience = profile_data.get("experience", [])
    projects = profile_data.get("projects", [])
    education = profile_data.get("education", [])
    summary = profile_data.get("summary", "")

    name = _esc(personal.get("name", "Candidate"))
    phone = _esc(personal.get("phone", ""))
    email = _esc(personal.get("email", ""))
    location = _esc(personal.get("location", ""))
    linkedin = personal.get("linkedin_url", "")
    github = personal.get("github_url", "")
    portfolio = personal.get("portfolio_url", "")

    # Build contact items
    contact_parts = []
    if phone:
        contact_parts.append(phone)
    if email:
        contact_parts.append(f'<a href="mailto:{_esc(email)}">{_esc(email)}</a>')
    if location:
        contact_parts.append(location)
    if linkedin:
        clean_li = linkedin.replace("https://www.linkedin.com/in/", "linkedin.com/in/").replace("https://linkedin.com/in/", "linkedin.com/in/")
        contact_parts.append(f'<a href="{_esc(linkedin)}" target="_blank">{_esc(clean_li)}</a>')
    if github:
        clean_gh = github.replace("https://github.com/", "github.com/").replace("https://www.github.com/", "github.com/")
        contact_parts.append(f'<a href="{_esc(github)}" target="_blank">{_esc(clean_gh)}</a>')
    if portfolio:
        contact_parts.append(f'<a href="{_esc(portfolio)}" target="_blank">Portfolio</a>')

    contact_html = ' <span class="sep">|</span> '.join(contact_parts)

    html_out = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{name} Resume</title>
<style>
  @page {{
    size: A4;
    margin: 0.35in 0.45in 0.35in 0.45in;
  }}
  * {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }}
  body {{
    font-family: 'Charter', 'Bitstream Charter', 'Georgia', 'Cambria', 'Times New Roman', serif;
    color: #111827;
    line-height: 1.32;
    font-size: 10pt;
    background: #ffffff;
    -webkit-print-color-adjust: exact;
  }}
  .header {{
    text-align: center;
    margin-bottom: 10px;
  }}
  .name {{
    font-size: 21pt;
    font-weight: 700;
    letter-spacing: 0.5px;
    margin-bottom: 3px;
    color: #000000;
    font-family: 'Charter', 'Georgia', serif;
  }}
  .contact {{
    font-size: 9.3pt;
    color: #374151;
  }}
  .contact a {{
    color: #1d4ed8;
    text-decoration: none;
  }}
  .contact span.sep {{
    margin: 0 4px;
    color: #6b7280;
  }}
  .section {{
    margin-top: 8px;
  }}
  .section-title {{
    font-size: 10.5pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    border-bottom: 1px solid #111;
    padding-bottom: 1.5px;
    margin-bottom: 5px;
    color: #000000;
  }}
  .item {{
    margin-bottom: 6px;
  }}
  .row {{
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 1px;
  }}
  .row-title {{
    font-weight: 700;
    font-size: 9.8pt;
    color: #111827;
  }}
  .row-meta {{
    font-weight: 400;
    font-size: 8.8pt;
    color: #374151;
    text-align: right;
  }}
  .row-subtitle {{
    font-style: italic;
    font-size: 9.2pt;
    color: #374151;
  }}
  ul.bullets {{
    margin-top: 2px;
    margin-bottom: 4px;
    padding-left: 17px;
  }}
  ul.bullets li {{
    font-size: 9pt;
    margin-bottom: 2px;
    line-height: 1.28;
    color: #1f2937;
  }}
  .skills-group {{
    font-size: 9.2pt;
    line-height: 1.45;
  }}
  .skills-label {{
    font-weight: 700;
    color: #000000;
  }}
  .summary-text {{
    font-size: 9.2pt;
    line-height: 1.35;
    color: #1f2937;
    margin-bottom: 4px;
  }}
</style>
</head>
<body>
  <div class="header">
    <div class="name">{name}</div>
    <div class="contact">
      {contact_html}
    </div>
  </div>
"""

    # Optional Professional Summary (if present)
    if summary:
        html_out += f"""
  <div class="section">
    <div class="section-title">Professional Summary</div>
    <div class="summary-text">{_esc(summary)}</div>
  </div>
"""

    # Education
    if education:
        html_out += '<div class="section"><div class="section-title">Education</div>'
        for edu in education:
            inst = _esc(edu.get("institution", ""))
            yr = _esc(edu.get("graduation_year", ""))
            deg = _esc(edu.get("degree", ""))
            field = _esc(edu.get("field_of_study", ""))
            sub = f"{deg} in {field}" if (deg and field) else (deg or field)
            html_out += f"""
        <div class="item">
          <div class="row">
            <div class="row-title">{inst}</div>
            <div class="row-meta">{yr}</div>
          </div>
          <div class="row">
            <div class="row-subtitle">{sub}</div>
            <div class="row-meta">{location}</div>
          </div>
        </div>"""
        html_out += '</div>'

    # Work Experience
    if experience:
        html_out += '<div class="section"><div class="section-title">Experience</div>'
        for exp in experience:
            role = _esc(exp.get("role", "Software Engineer"))
            company = _esc(exp.get("company", ""))
            loc = _esc(exp.get("location", ""))
            s_date = _esc(exp.get("start_date", ""))
            e_date = _esc(exp.get("end_date", "Present"))
            dates = f"{s_date} – {e_date}" if s_date else e_date
            html_out += f"""
        <div class="item">
          <div class="row">
            <div class="row-title">{role}</div>
            <div class="row-meta">{dates}</div>
          </div>
          <div class="row">
            <div class="row-subtitle">{company}</div>
            <div class="row-meta">{loc}</div>
          </div>
          <ul class="bullets">"""
            for h in exp.get("highlights", []):
                html_out += f"<li>{_esc(h)}</li>"
            html_out += """
          </ul>
        </div>"""
        html_out += '</div>'

    # Projects
    if projects:
        html_out += '<div class="section"><div class="section-title">Projects</div>'
        for proj in projects:
            title = _esc(proj.get("title", ""))
            stack_list = proj.get("tech_stack", [])
            stack_str = ", ".join([_esc(s) for s in stack_list])
            html_out += f"""
        <div class="item">
          <div class="row">
            <div class="row-title">{title} <span style="font-weight: normal; font-style: italic; color: #4b5563;">| {stack_str}</span></div>
          </div>"""
            if proj.get("description"):
                html_out += f"<div style='font-size: 8.8pt; color: #374151; margin-top: 1px;'>{_esc(proj.get('description'))}</div>"
            achievements = proj.get("key_achievements", [])
            if achievements:
                html_out += '<ul class="bullets">'
                for ach in achievements:
                    html_out += f"<li>{_esc(ach)}</li>"
                html_out += '</ul>'
            html_out += '</div>'
        html_out += '</div>'

    # Technical Skills
    html_out += '<div class="section"><div class="section-title">Technical Skills</div><div class="skills-group">'
    if skills.get("programming_languages"):
        langs = ", ".join([_esc(x) for x in skills["programming_languages"]])
        html_out += f"<div><span class='skills-label'>Languages:</span> {langs}</div>"
    if skills.get("frameworks_and_libraries"):
        fw = ", ".join([_esc(x) for x in skills["frameworks_and_libraries"]])
        html_out += f"<div><span class='skills-label'>Frameworks & Libraries:</span> {fw}</div>"
    if skills.get("ai_and_ml"):
        aiml = ", ".join([_esc(x) for x in skills["ai_and_ml"]])
        html_out += f"<div><span class='skills-label'>AI, ML & Automation:</span> {aiml}</div>"
    db_tools = skills.get("databases", []) + skills.get("tools_and_platforms", [])
    if db_tools:
        dbt = ", ".join([_esc(x) for x in db_tools])
        html_out += f"<div><span class='skills-label'>Databases & Tools:</span> {dbt}</div>"
    html_out += '</div></div>'

    html_out += """
</body>
</html>"""
    return html_out


def render_html_to_pdf_bytes(html_content: str) -> bytes:
    """
    Compiles an HTML resume string into a vector PDF using Playwright Chromium headless.
    """
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_content(html_content, wait_until="networkidle")
            pdf_bytes = page.pdf(
                format="A4",
                print_background=True,
                prefer_css_page_size=True,
            )
            return pdf_bytes
        finally:
            browser.close()


def generate_candidate_master_pdf(profile_data: Dict[str, Any], output_filename: str = "master_resume.pdf") -> str:
    """
    Generates and saves the master candidate PDF in output/resumes/.
    Returns the absolute path of the generated PDF.
    """
    resumes_dir = OUTPUT_DIR / "resumes"
    resumes_dir.mkdir(parents=True, exist_ok=True)
    target_path = resumes_dir / output_filename

    html_str = generate_resume_html(profile_data)
    pdf_bytes = render_html_to_pdf_bytes(html_str)
    target_path.write_bytes(pdf_bytes)
    logger.info(f"Generated candidate master PDF at {target_path} ({len(pdf_bytes)} bytes)")
    return str(target_path.resolve())
