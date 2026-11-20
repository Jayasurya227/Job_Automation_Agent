"""
Automated Test Suite for Step 3.2: Multi-Portal Job Scraper & Discovery Engine.
Verifies multi-portal extraction, DiscoveredJob schemas, and SQLite deduplication.
"""

import sys
import asyncio
from pathlib import Path

# Safe Windows stdout encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Ensure backend root is on path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.agent.scraper import (
    DiscoveredJob,
    load_candidate_preferences,
    _run_jobspy_sync,
    discover_jobs,
)
from app.db.session import SessionLocal
from app.db.crud import create_job, delete_job, job_exists


async def run_tests():
    print("=" * 60)
    print("[TEST SUITE] STEP 3.2: MULTI-PORTAL SCRAPER & DISCOVERY ENGINE")
    print("=" * 60)

    passed = 0
    total = 5

    # ---------------------------------------------------------
    # TEST 1: Candidate Preferences Loading
    # ---------------------------------------------------------
    print("\n[Test 1/5] Verifying profile preference loading...")
    prefs = load_candidate_preferences()
    assert "target_roles" in prefs, "Missing target_roles in loaded preferences"
    assert len(prefs["target_roles"]) > 0, "Empty target_roles in profile"
    print(f"  [OK] Target roles loaded: {prefs['target_roles']}")
    print(f"  [OK] Preferred locations: {prefs.get('preferred_locations')}")
    passed += 1

    # ---------------------------------------------------------
    # TEST 2: DiscoveredJob Model Validation
    # ---------------------------------------------------------
    print("\n[Test 2/5] Verifying DiscoveredJob Pydantic schema...")
    mock_job = DiscoveredJob(
        title="Junior AI Engineer",
        company="NextGen AI Labs",
        location="Hyderabad, India",
        portal="linkedin",
        job_url="https://linkedin.com/jobs/view/12345678",
        description="We are seeking a Python and LLM engineer with FastAPI experience.",
        salary="INR 8,00,000 - 12,00,000 /year",
        date_posted="2026-09-26",
    )
    assert mock_job.title == "Junior AI Engineer"
    assert mock_job.portal == "linkedin"
    assert "LLM" in mock_job.description
    print("  [OK] DiscoveredJob validation and attribute access verified.")
    passed += 1

    # ---------------------------------------------------------
    # TEST 3: Smart Deduplication against SQLite
    # ---------------------------------------------------------
    print("\n[Test 3/5] Verifying smart SQLite deduplication...")
    db = SessionLocal()
    test_job_id = None
    try:
        # Insert a known test job
        test_job = create_job(
            db=db,
            job_title="Test Unique Role XYZ",
            company_name="Antigravity Test Corp",
            job_description="Testing deduplication logic.",
            job_url="https://example.com/jobs/test-unique-xyz-101",
        )
        test_job_id = test_job.id

        # Check deduplication by URL
        assert job_exists(db, job_url="https://example.com/jobs/test-unique-xyz-101") is True
        print("  [OK] Correctly flagged duplicate by URL.")

        # Check deduplication by Title + Company
        assert job_exists(db, title="Test Unique Role XYZ", company="Antigravity Test Corp") is True
        print("  [OK] Correctly flagged duplicate by Title + Company.")

        # Check that unseen job returns False
        assert job_exists(db, job_url="https://example.com/jobs/brand-new-job-404") is False
        print("  [OK] Correctly identified unseen job as non-duplicate.")
        passed += 1

    finally:
        if test_job_id:
            delete_job(db, test_job_id)
            print("  [*] Cleaned up test job record from SQLite.")
        db.close()

    # ---------------------------------------------------------
    # TEST 4: JobSpy Aggregator Execution
    # ---------------------------------------------------------
    print("\n[Test 4/5] Verifying JobSpy multi-portal scraper execution...")
    # Run a targeted small query across LinkedIn & Indeed
    results = await asyncio.to_thread(
        _run_jobspy_sync,
        search_term="Python Developer",
        location="Remote",
        portals=["linkedin", "indeed"],
        results_wanted=3,
        country="USA",
        hours_old=72,
    )
    assert isinstance(results, list), "Expected list result from JobSpy"
    print(f"  [OK] JobSpy executed successfully. Listings fetched: {len(results)}")
    if len(results) > 0:
        first = results[0]
        print(f"  Sample Job: '{first.title}' at '{first.company}' ({first.portal.upper()})")
    passed += 1

    # ---------------------------------------------------------
    # TEST 5: Autonomous Discovery Coordinator Pipeline
    # ---------------------------------------------------------
    print("\n[Test 5/5] Verifying discover_jobs coordinator with deduplication...")
    discovered = await discover_jobs(
        search_term="Python Developer",
        location="Remote",
        portals=["linkedin"],
        results_per_portal=3,
        deduplicate=True,
    )
    assert isinstance(discovered, list)
    print(f"  [OK] discover_jobs returned {len(discovered)} unique jobs after deduplication.")
    passed += 1

    print("\n" + "=" * 60)
    print(f"[RESULT] STEP 3.2 TESTS RESULT: {passed}/{total} PASSED")
    print("=" * 60)
    assert passed == total, f"Expected {total} passed tests, but got {passed}"


if __name__ == "__main__":
    asyncio.run(run_tests())
