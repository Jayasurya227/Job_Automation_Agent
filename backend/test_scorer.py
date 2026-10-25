"""
Module: test_scorer.py
Purpose: Step 1.3 Verification - Tests Job Description Analyzer with High-Fit and Low-Fit Roles.
Standards: Rule 1 (Senior Validation), Rule 2 (Schema Enforcement), Rule 3 (Low Code & High Signal).
"""
import sys
from app.agent.scorer import analyze_and_score_job

# Scenario 1: Highly relevant role matching Jai's background
HIGH_MATCH_JD = """
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

# Scenario 2: Unrelated senior enterprise role to verify anti-hallucination & accurate rejection
LOW_MATCH_JD = """
Job Title: Senior Java Enterprise Architect
Company: Legacy Systems Global
Location: Bengaluru
Requirements:
- Minimum 10+ years of enterprise software engineering experience.
- Deep expertise in Java 17+, Spring Boot, Spring Cloud, and Hibernate.
- Hands-on mastery of Kubernetes cluster administration and Apache Kafka streaming at scale.
- Proven track record of managing engineering teams of 15+ developers.
"""

def print_result_card(scenario_name: str, result):
    print("\n" + "=" * 65)
    print(f"  SCENARIO: {scenario_name}")
    print("=" * 65)
    print(f"  Detected Role    : {result.job_title} ({result.company_name})")
    print(f"  Match Score      : {result.match_score}%")
    print(f"  Recommendation   : {result.recommendation}")
    print(f"  Matching Skills  : {', '.join(result.matching_skills)}")
    print(f"  Missing Skills   : {', '.join(result.missing_skills) if result.missing_skills else 'None'}")
    print(f"  Reasoning        : {result.summary_reasoning}")
    print("=" * 65)

def run_tests():
    print("\n[INFO] Starting Step 1.3 AI Scorer Verification...")
    
    # 1. Test High Match
    print("\n[TEST 1/2] Evaluating High-Fit AI Engineer Role...")
    res_high = analyze_and_score_job(HIGH_MATCH_JD)
    print_result_card("HIGH-FIT ROLE (Junior AI Engineer)", res_high)
    assert res_high.recommendation in ["Apply", "Review"], "High-fit role should be recommended for Apply or Review"
    assert res_high.match_score >= 65, "High-fit role match score should be >= 65%"

    # 2. Test Low Match
    print("\n[TEST 2/2] Evaluating Low-Fit 10-Yr Java Role...")
    res_low = analyze_and_score_job(LOW_MATCH_JD)
    print_result_card("LOW-FIT ROLE (Senior Java Architect)", res_low)
    assert res_low.recommendation == "Skip", "Low-fit role should be Skip"
    assert res_low.match_score < 50, "Low-fit role match score should be < 50%"

    print("\n[SUCCESS] All Step 1.3 Scorer Tests Passed Cleanly!\n")

if __name__ == "__main__":
    try:
        run_tests()
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] Test failed with error: {e}")
        sys.exit(1)
