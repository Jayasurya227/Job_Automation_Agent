"""
Automated Test Suite for Step 3.3: Autonomous Ingestion & AI Scoring Pipeline.
Verifies auto-triage routing, Gemini scoring, resume generation, and SQLite persistence.
"""

import sys
import asyncio
import time
from pathlib import Path

# Safe Windows stdout encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Ensure backend root is on path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agent.scraper import DiscoveredJob
from app.agent.ingestion import (
    IngestionJobResult,
    IngestionReport,
    ingest_single_job,
    run_autonomous_ingestion,
)
from app.db.session import SessionLocal
from app.db.models import Job
from app.db.crud import get_job, delete_job


async def run_tests():
    print("=" * 60)
    print("[TEST SUITE] STEP 3.3: AUTONOMOUS INGESTION & AI SCORING")
    print("=" * 60)

    passed = 0
    total = 5

    # Pre-test cleanup of any leftover test jobs
    init_db = SessionLocal()
    try:
        leftover_jobs = init_db.query(Job).filter(Job.job_url.like("%example.com/jobs/%")).all()
        for j in leftover_jobs:
            delete_job(init_db, j.id)
        if leftover_jobs:
            print(f"[*] Pre-cleaned {len(leftover_jobs)} leftover test records from SQLite.")
    finally:
        init_db.close()

    # ---------------------------------------------------------
    # TEST 1: Ingestion Models Validation
    # ---------------------------------------------------------
    print("\n[Test 1/5] Verifying Ingestion data models...")
    res = IngestionJobResult(
        job_id=999,
        title="Test Engineer",
        company="Test Corp",
        portal="linkedin",
        match_score=85,
        status="Ready",
        recommendation="Apply",
        resume_tex_path="output/resumes/test.tex",
    )
    assert res.job_id == 999
    assert res.status == "Ready"
    report = IngestionReport(total_discovered=1, high_matches_ready=1, jobs=[res])
    assert report.total_discovered == 1
    print("  [OK] Ingestion models serialized and validated.")
    passed += 1

    # ---------------------------------------------------------
    # TEST 2: High Match Auto-Triage (>= 75% -> Ready)
    # ---------------------------------------------------------
    print("\n[Test 2/5] Testing High-Match Auto-Triage (>= 75% -> Ready)...")
    high_match_job = DiscoveredJob(
        title="Junior AI / Python Developer",
        company="InnoTech AI Labs",
        location="Remote, India",
        portal="linkedin",
        job_url="https://linkedin.com/jobs/view/test-high-match-99901",
        description=(
            "We are seeking a Junior AI Developer skilled in Python, FastAPI, and LLM integrations. "
            "Experience with RAG, LangChain, SQLite, and prompt engineering is highly desirable. "
            "Immediate joiners preferred for remote work."
        ),
        salary="INR 8,00,000 - 12,00,000 /year",
    )

    high_result = await ingest_single_job(high_match_job, min_match_score=75)
    created_id_high = None
    try:
        assert high_result is not None, "Failed to ingest high-match job"
        created_id_high = high_result.job_id
        assert high_result.match_score >= 75, f"Expected high score >= 75, got {high_result.match_score}"
        assert high_result.status == "Ready", f"Expected Ready status, got {high_result.status}"
        assert high_result.resume_pdf_path is not None or high_result.resume_tex_path is not None, "Resume path should be populated"

        # Verify database record
        db = SessionLocal()
        try:
            db_job = get_job(db, created_id_high)
            assert db_job is not None
            assert len(db_job.applications) > 0
            assert db_job.applications[0].status == "Ready"
            print(f"  [OK] Job ID {created_id_high} auto-triaged to 'Ready' with score {high_result.match_score}%.")
            print(f"       Tailored Resume: {high_result.resume_pdf_path or high_result.resume_tex_path}")
        finally:
            db.close()
        passed += 1

    finally:
        if created_id_high:
            db = SessionLocal()
            delete_job(db, created_id_high)
            db.close()
            print("  [*] Cleaned up high-match test job from SQLite.")

    # ---------------------------------------------------------
    # TEST 3: Low Match Auto-Triage (< 75% -> Archived)
    # ---------------------------------------------------------
    print("\n[Test 3/5] Testing Low-Match Auto-Triage (< 75% -> Archived)...")
    low_match_job = DiscoveredJob(
        title="Senior Offshore Petroleum Drilling Specialist",
        company="Oceanic Deep Drilling Inc",
        location="Offshore Rig, Mumbai High",
        portal="indeed",
        job_url="https://indeed.com/viewjob?jk=test-low-match-99902",
        description=(
            "Seeking licensed Offshore Drilling Engineer with 10+ years experience in deepwater wells, "
            "rotary drilling, blowout preventers, mud engineering, and offshore rig safety certifications. "
            "Must hold valid BOSIET and HUET offshore safety certifications."
        ),
    )

    low_result = await ingest_single_job(low_match_job, min_match_score=75)
    created_id_low = None
    try:
        assert low_result is not None, "Failed to ingest low-match job"
        created_id_low = low_result.job_id
        assert low_result.match_score < 75, f"Expected low score < 75, got {low_result.match_score}"
        assert low_result.status == "Archived", f"Expected Archived status, got {low_result.status}"
        assert low_result.resume_tex_path is None, "Resume should NOT be tailored for low-match job"

        # Verify database record
        db = SessionLocal()
        try:
            db_job = get_job(db, created_id_low)
            assert db_job is not None
            assert len(db_job.applications) > 0
            assert db_job.applications[0].status == "Archived"
            print(f"  [OK] Job ID {created_id_low} auto-triaged to 'Archived' with score {low_result.match_score}%.")
            print("       Zero resources wasted on resume tailoring.")
        finally:
            db.close()
        passed += 1

    finally:
        if created_id_low:
            db = SessionLocal()
            delete_job(db, created_id_low)
            db.close()
            print("  [*] Cleaned up low-match test job from SQLite.")

    # ---------------------------------------------------------
    # TEST 4: Deduplication Protection in Ingestion
    # ---------------------------------------------------------
    print("\n[Test 4/5] Testing duplicate rejection in ingestion...")
    ts = int(time.time() * 1000)
    unique_dup_url = f"https://example.com/jobs/dup-test-{ts}"
    unique_dup_title = f"Python Developer {ts}"
    unique_dup_company = f"CloudScale Systems {ts}"
    test_dup_job = DiscoveredJob(
        title=unique_dup_title,
        company=unique_dup_company,
        location="Remote",
        portal="glassdoor",
        job_url=unique_dup_url,
        description="FastAPI and React developer position with Python and SQLite experience.",
    )

    res1 = await ingest_single_job(test_dup_job, min_match_score=75)
    assert res1 is not None, "First insertion failed"
    dup_id = res1.job_id

    try:
        # Ingesting exact same job second time should return None
        res2 = await ingest_single_job(test_dup_job, min_match_score=75)
        assert res2 is None, "Duplicate job was not rejected by ingestion pipeline"
        print("  [OK] Successfully rejected duplicate job without creating redundant records.")
        passed += 1
    finally:
        db = SessionLocal()
        delete_job(db, dup_id)
        db.close()
        print("  [*] Cleaned up deduplication test job from SQLite.")

    # ---------------------------------------------------------
    # TEST 5: Batch Ingestion Runner & Aggregate Report
    # ---------------------------------------------------------
    print("\n[Test 5/5] Testing batch autonomous ingestion runner...")
    ts_b = int(time.time() * 1000)
    unique_batch_url = f"https://example.com/jobs/batch-test-{ts_b}"
    batch_jobs = [
        DiscoveredJob(
            title=f"AI Automation Specialist {ts_b}",
            company=f"SmartAgent AI {ts_b}",
            location="Remote",
            portal="linkedin",
            job_url=unique_batch_url,
            description="Developing agent workflows with LangGraph, Playwright, Python, and Gemini LLMs.",
        ),
    ]

    report = await run_autonomous_ingestion(
        discovered_jobs=batch_jobs,
        min_match_score=75,
        max_jobs_to_process=1,
    )
    assert isinstance(report, IngestionReport)
    assert report.total_discovered == 1
    assert len(report.jobs) == 1
    print(f"  [OK] Batch report summary: {report.high_matches_ready} Ready, "
          f"{report.low_matches_archived} Archived, {report.duplicates_skipped} Duplicates skipped.")
    passed += 1

    # Cleanup batch test jobs
    db = SessionLocal()
    for j in report.jobs:
        delete_job(db, j.job_id)
    db.close()
    print("  [*] Cleaned up batch test records.")

    print("\n" + "=" * 60)
    print(f"[RESULT] STEP 3.3 TESTS RESULT: {passed}/{total} PASSED")
    print("=" * 60)
    assert passed == total, f"Expected {total} passed tests, but got {passed}"


if __name__ == "__main__":
    asyncio.run(run_tests())
