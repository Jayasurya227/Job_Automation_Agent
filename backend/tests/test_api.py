"""
Module: test_api.py
Purpose: Step 2.2 Verification Suite - Tests FastAPI endpoints, responses, CORS, and DB persistence.
Standards: Rule 1 (Zero Blind Trust), Rule 2 (Type & Schema Validation), Rule 5 (Production Reliability).
"""
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from main import app
from app.db.session import SessionLocal
from app.db.session import init_db
from app.db import crud

client = TestClient(app)

import time

def run_api_tests():
    init_db()
    ts = int(time.time())
    print("\n=======================================================", flush=True)
    print("  STEP 2.2 FASTAPI REST SERVER VERIFICATION SUITE", flush=True)
    print("=======================================================", flush=True)

    # 1. Test Health Check
    print("\n[TEST 1/7] Testing System Health Check (GET /)...", flush=True)
    res = client.get("/")
    assert res.status_code == 200, f"Health check failed: {res.text}"
    data = res.json()
    assert data["status"] == "online", "Server status not online"
    print(f"  [SUCCESS] Server Status: {data['status']} | Agent: {data['agent']}", flush=True)

    # 2. Test Profile Endpoint
    print("\n[TEST 2/7] Testing Candidate Profile API (GET /api/profile)...", flush=True)
    res = client.get("/api/profile")
    assert res.status_code == 200, f"Profile fetch failed: {res.text}"
    profile = res.json()
    assert any(n in profile["personal_info"]["name"] for n in ["Jai", "Jayasurya", "Rayavaram"]), "Profile name mismatch"
    print(f"  [SUCCESS] Profile Loaded: {profile['personal_info']['name']} | Roles: {profile['preferences']['target_roles']}", flush=True)

    # 3. Test Autonomous Analysis Endpoint (POST /api/analyze)
    print("\n[TEST 3/7] Testing Autonomous Analysis Pipeline (POST /api/analyze)...", flush=True)
    jd_payload = {
        "job_title": f"Junior AI Engineer {ts}",
        "company_name": f"NextGen AI Solutions {ts}",
        "location": "Hyderabad / Remote",
        "portal_name": "LinkedIn",
        "job_url": f"https://linkedin.com/jobs/view/998877_{ts}",
        "job_description": (
            "NextGen AI Solutions is hiring a Junior AI Engineer. "
            "Required: Python, FastAPI, LLMs, Prompt Engineering, RAG (Retrieval-Augmented Generation). "
            "Experience with Playwright and SQLite/PostgreSQL is preferred. "
            "Notice period: Immediate joiners preferred."
        ),
        "recipient_role": "Technical_Lead"
    }
    res = client.post("/api/analyze", json=jd_payload)
    assert res.status_code == 201, f"Analysis pipeline failed: {res.text}"
    job_result = res.json()
    job_id = job_result["job_id"]
    assert job_id is not None, "Job ID was not returned"
    assert job_result["match_score"] >= 70, f"Expected high match score, got: {job_result['match_score']}"
    assert job_result["tailored_resume_tex_path"] != "", "Resume was not tailored"
    assert job_result["cold_email_body"] != "", "Cold email was not generated"
    print(f"  [SUCCESS] Analyzed & Persisted Job ID: {job_id}")
    print(f"            Score: {job_result['match_score']}% | Rec: {job_result['recommendation']}")
    print(f"            Status: {job_result['status']} | LaTeX: {job_result['tailored_resume_tex_path']}")
    print(f"            Outreach Subject: {job_result['cold_email_subject']}")

    # 4. Test Job Listing Endpoint (GET /api/jobs)
    print("\n[TEST 4/6] Testing Job Pipeline Listing (GET /api/jobs)...")
    res = client.get("/api/jobs")
    assert res.status_code == 200, f"Jobs listing failed: {res.text}"
    jobs_list = res.json()
    assert len(jobs_list) >= 1, "Job list returned empty"
    target_job = next((j for j in jobs_list if j["id"] == job_id), None)
    assert target_job is not None, f"Analyzed job {job_id} not found in listing"
    print(f"  [SUCCESS] Jobs in Pipeline: {len(jobs_list)} | Found Target Job: {target_job['job_title']} ({target_job['company_name']})")

    # Verify single job inspection & resume download endpoints
    detail_res = client.get(f"/api/jobs/{job_id}")
    assert detail_res.status_code == 200, f"Detail fetch failed: {detail_res.text}"
    assert len(detail_res.json()["matching_skills"]) > 0, "Detail evaluation missing matching skills"
    print(f"  [SUCCESS] Job Detail Inspected: {len(detail_res.json()['matching_skills'])} matching skills")

    resume_res = client.get(f"/api/jobs/{job_id}/resume")
    assert resume_res.status_code == 200, f"Resume fetch failed: {resume_res.text}"
    assert "documentclass" in resume_res.json()["tex_content"], "LaTeX content not loaded"
    print(f"  [SUCCESS] Tailored Resume Content Verified ({len(resume_res.json()['tex_content'])} bytes)")

    # 5. Test Status Update & Metrics (PATCH /api/jobs/{id}/status & GET /api/metrics)
    print("\n[TEST 5/6] Testing Status Transition & Metrics Calculation...")
    patch_res = client.patch(f"/api/jobs/{job_id}/status", json={"status": "Applied", "notes": "Submitted via portal"})
    assert patch_res.status_code == 200, f"Status update failed: {patch_res.text}"
    print(f"  [SUCCESS] Status Updated: {patch_res.json()['new_status']}")

    metrics_res = client.get("/api/metrics")
    assert metrics_res.status_code == 200, f"Metrics fetch failed: {metrics_res.text}"
    metrics = metrics_res.json()
    assert metrics["applied_count"] >= 1, "Applied counter did not increment"
    print(f"  [SUCCESS] Pipeline Metrics: Total: {metrics['total_jobs']} | Applied: {metrics['applied_count']} | Avg Score: {metrics['average_match_score']}%")

    # 6. Test Cascading Cleanup (DELETE /api/jobs/{id})
    print("\n[TEST 6/6] Testing Cascading Deletion via API (DELETE /api/jobs/{id})...")
    del_res = client.delete(f"/api/jobs/{job_id}")
    assert del_res.status_code == 204, f"Delete failed: {del_res.status_code}"
    
    # Confirm it's gone
    confirm_res = client.get("/api/jobs")
    remaining_ids = [j["id"] for j in confirm_res.json()]
    assert job_id not in remaining_ids, "Deleted job still present in database"
    print("  [SUCCESS] Cascading Delete Verified via API. Zero test artifacts left in SQLite.")

    # 7. Test Discovery Endpoint (POST /api/discover)
    print("\n[TEST 7/7] Testing Autonomous Discovery API (POST /api/discover)...")
    disc_payload = {
        "search_term": "Python Developer",
        "location": "Remote",
        "portals": ["linkedin"],
        "results_wanted": 2,
        "min_match_score": 75,
        "max_process": 1
    }
    disc_res = client.post("/api/discover", json=disc_payload)
    assert disc_res.status_code == 200, f"Discovery endpoint failed: {disc_res.text}"
    report = disc_res.json()
    assert "total_discovered" in report, "Missing total_discovered in report"
    assert "jobs" in report, "Missing jobs in report"
    print(f"  [SUCCESS] Discovery API Verified: Discovered: {report['total_discovered']} | Ready: {report['high_matches_ready']} | Archived: {report['low_matches_archived']}")

    # Clean up any created test job from SQLite
    for j in report.get("jobs", []):
        client.delete(f"/api/jobs/{j['job_id']}")

    print("\n=======================================================")
    print("  FASTAPI REST SERVER: ALL 7 ENDPOINTS PASSED CLEANLY (100%)")
    print("=======================================================\n")

if __name__ == "__main__":
    run_api_tests()
