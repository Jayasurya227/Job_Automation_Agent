"""
Module: test_outreach.py
Purpose: Step 1.5 Verification - Tests Personalized Cold Outreach (Tech Lead vs HR Recruiter).
Standards: Rule 1 (Senior Scrutiny), Rule 2 (Validation), Rule 3 (Low Code & High Signal).
"""
import sys
from app.agent.scorer import analyze_and_score_job
from app.agent.outreach import generate_outreach

TARGET_JD = """
Job Title: Junior AI Engineer
Company: NextGen AI Solutions
Location: Hyderabad / Remote
About the Role:
We are seeking a motivated Junior AI Engineer to help build our AI-powered automation products.
Requirements:
- Strong programming skills in Python and familiarity with asynchronous programming.
- Hands-on experience working with LLMs, prompt engineering, and RAG (Retrieval-Augmented Generation).
- Experience building RESTful backend services with FastAPI.
- Familiarity with web automation tools like Playwright or Selenium is a strong plus.
- Experience with databases like SQLite or PostgreSQL.
- Collaborative team player with good problem-solving ability. Immediate joiners preferred.
"""

def print_outreach_card(persona_title: str, outreach):
    word_count = len(outreach.cold_email_body.split())
    char_count = len(outreach.linkedin_connection_note)
    print("\n" + "=" * 65)
    print(f"  OUTREACH PERSONA: {persona_title}")
    print("=" * 65)
    print(f"  Target Hook     : {outreach.highlighted_project}")
    print(f"  Subject Line    : {outreach.subject_line}")
    print(f"  Email Body      :\n{outreach.cold_email_body}")
    print(f"  [Word Count]    : {word_count} words")
    print("-" * 65)
    print(f"  LinkedIn Note   :\n{outreach.linkedin_connection_note}")
    print(f"  [Char Count]    : {char_count}/280 characters")
    print(f"  Call To Action  : {outreach.call_to_action}")
    print("=" * 65)

def test_outreach_generation():
    print("\n[INFO] Starting Step 1.5 Outreach Generator Verification...")
    
    # 1. Score job
    match = analyze_and_score_job(TARGET_JD)
    
    # 2. Test Technical Lead Persona
    print("\n[TEST 1/2] Generating Outreach for Technical Lead / Engineering Manager...")
    tech_outreach = generate_outreach(
        job_description=TARGET_JD,
        match_result=match,
        recipient_name="David (Engineering Manager)",
        recipient_role="Technical_Lead"
    )
    print_outreach_card("TECHNICAL LEAD / ENGINEERING MANAGER", tech_outreach)
    assert len(tech_outreach.linkedin_connection_note) <= 280, "LinkedIn note must be <= 280 characters"

    # 3. Test HR Recruiter Persona
    print("\n[TEST 2/2] Generating Outreach for HR Recruiter...")
    hr_outreach = generate_outreach(
        job_description=TARGET_JD,
        match_result=match,
        recipient_name="Priya (Talent Acquisition)",
        recipient_role="HR_Recruiter"
    )
    print_outreach_card("TALENT ACQUISITION / HR RECRUITER", hr_outreach)
    assert len(hr_outreach.linkedin_connection_note) <= 280, "LinkedIn note must be <= 280 characters"

    print("\n[SUCCESS] All Step 1.5 Cold Outreach Tests Passed Cleanly!\n")

if __name__ == "__main__":
    try:
        test_outreach_generation()
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] Outreach Test failed: {e}")
        sys.exit(1)
