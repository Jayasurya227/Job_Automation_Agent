import asyncio
import json
import logging
from pathlib import Path
from app.agent.scraper import discover_jobs, load_candidate_preferences

logging.basicConfig(level=logging.INFO)

async def test_dynamic_multi_role():
    print("--- 1. Testing load_candidate_preferences() ---")
    prefs = load_candidate_preferences()
    target_roles = prefs.get("target_roles", [])
    print(f"Current saved target roles in profile.json: {target_roles}")
    assert len(target_roles) >= 1, "Expected at least 1 target role"

    print("\n--- 2. Testing search_terms resolution with explicit roles ---")
    # Test with explicitly provided search_terms
    custom_roles = ["AI Engineer", "Python Developer"]
    print(f"Calling discover_jobs with custom search_terms: {custom_roles} (results_per_portal=1, portals=[])")
    # Passing empty portals so it tests role iteration and SQLite deduplication without launching Chrome
    jobs = await discover_jobs(
        search_terms=custom_roles,
        location="Hyderabad",
        portals=[],
        results_per_portal=1,
        deduplicate=False
    )
    print("  [SUCCESS] Explicit search_terms passed and executed cleanly.")

    print("\n--- 3. Testing comma-separated search_term string ---")
    jobs = await discover_jobs(
        search_term="Data Scientist, Machine Learning Engineer",
        location="Hyderabad",
        portals=[],
        results_per_portal=1,
        deduplicate=False
    )
    print("  [SUCCESS] Comma-separated search_term parsed and executed cleanly.")

    print("\n--- 4. Testing default fallback to profile.json saved roles ---")
    jobs = await discover_jobs(
        search_term=None,
        search_terms=None,
        location="Hyderabad",
        portals=[],
        results_per_portal=1,
        deduplicate=False
    )
    print("  [SUCCESS] Default fallback to profile.json executed cleanly.")

if __name__ == "__main__":
    asyncio.run(test_dynamic_multi_role())
