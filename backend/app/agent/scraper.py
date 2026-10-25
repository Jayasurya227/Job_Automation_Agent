"""
Autonomous Multi-Portal Job Scraper & Discovery Engine.
Integrates JobSpy high-speed aggregation with Playwright stealth browser extraction.
Supports LinkedIn, Indeed, Naukri, Glassdoor, and ZipRecruiter.
Includes smart deduplication against SQLite jobs.db and anti-bot pacing.
Part of Phase 3: Browser Automation & Job Discovery.
"""

import re
import json
import logging
import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from app.agent.browser import browser_manager
from app.db.session import SessionLocal
from app.db.crud import job_exists

logger = logging.getLogger("agent.scraper")

PROFILE_PATH = Path(__file__).resolve().parent.parent.parent / "profile.json"


class DiscoveredJob(BaseModel):
    """Normalized data model for a job discovered across any portal."""
    title: str = Field(..., description="Job title")
    company: str = Field(..., description="Company or hiring organization")
    location: str = Field(default="", description="Location or remote indicator")
    portal: str = Field(..., description="Portal name: linkedin, indeed, naukri, glassdoor, etc.")
    job_url: str = Field(..., description="Direct URL to the job listing")
    description: str = Field(default="", description="Full or excerpt job description")
    salary: str = Field(default="", description="Advertised salary or compensation info")
    date_posted: str = Field(default="", description="Date posted or age of listing")


def load_candidate_preferences() -> Dict[str, Any]:
    """Loads target job titles and locations from profile.json."""
    if not PROFILE_PATH.exists():
        return {
            "target_roles": ["Python Developer", "Junior AI Engineer"],
            "preferred_locations": ["India", "Remote"],
        }
    try:
        with open(PROFILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("preferences", {})
    except Exception as e:
        logger.warning(f"Could not load preferences from profile.json: {e}")
        return {
            "target_roles": ["Python Developer", "Junior AI Engineer"],
            "preferred_locations": ["India", "Remote"],
        }


def _run_jobspy_sync(
    search_term: str,
    location: str,
    portals: List[str],
    results_wanted: int,
    country: str,
    hours_old: int = 72,
) -> List[DiscoveredJob]:
    """
    Synchronous wrapper to execute JobSpy scrape_jobs safely inside a worker thread.
    """
    try:
        from jobspy import scrape_jobs
    except ImportError:
        logger.error("JobSpy is not installed. Install with 'pip install python-jobspy'")
        return []

    # Map portal names to JobSpy supported site names
    valid_sites = []
    site_mapping = {
        "linkedin": "linkedin",
        "indeed": "indeed",
        "glassdoor": "glassdoor",
        "zip_recruiter": "zip_recruiter",
        "ziprecruiter": "zip_recruiter",
    }

    for p in portals:
        p_norm = p.lower().strip()
        if p_norm in site_mapping:
            valid_sites.append(site_mapping[p_norm])

    if not valid_sites:
        valid_sites = ["indeed", "linkedin"]

    country_indeed = "India" if "india" in location.lower() or country.lower() == "india" else "USA"

    try:
        logger.info(f"Running JobSpy for '{search_term}' in '{location}' across {valid_sites} (target: {results_wanted})...")
        df = scrape_jobs(
            site_name=valid_sites,
            search_term=search_term,
            location=location,
            results_wanted=results_wanted,
            hours_old=hours_old,
            country_indeed=country_indeed,
        )

        if df is None or df.empty:
            logger.info("JobSpy returned 0 results.")
            return []

        discovered = []
        for _, row in df.iterrows():
            title = str(row.get("title", "") or "").strip()
            company = str(row.get("company", "") or "").strip()
            job_url = str(row.get("job_url", "") or "").strip()
            desc = str(row.get("description", "") or "").strip()
            loc = str(row.get("location", "") or "").strip()
            site = str(row.get("site", "") or "Aggregator").lower().strip()

            # Format compensation if available
            min_amt = row.get("min_amount")
            max_amt = row.get("max_amount")
            interval = row.get("interval")
            currency = row.get("currency", "")
            salary_str = ""
            if min_amt and str(min_amt) != "nan":
                salary_str = f"{currency} {min_amt}"
                if max_amt and str(max_amt) != "nan":
                    salary_str += f" - {max_amt}"
                if interval and str(interval) != "nan":
                    salary_str += f" /{interval}"

            date_posted = str(row.get("date_posted", "") or "")

            if title and company and job_url:
                discovered.append(
                    DiscoveredJob(
                        title=title,
                        company=company,
                        location=loc or location,
                        portal=site,
                        job_url=job_url,
                        description=desc,
                        salary=salary_str,
                        date_posted=date_posted,
                    )
                )

        logger.info(f"JobSpy successfully extracted {len(discovered)} raw job listings.")
        return discovered

    except Exception as e:
        logger.error(f"JobSpy scraping error: {e}", exc_info=True)
        return []


async def scrape_naukri_playwright(
    search_term: str,
    location: str = "India",
    results_wanted: int = 10,
) -> List[DiscoveredJob]:
    """
    Stealth Playwright scraper for Naukri.com using human-like interaction.
    Navigates to the search listing, smoothly scrolls, and extracts DOM job tuples.
    """
    # Clean keyword and location for URL
    clean_keyword = re.sub(r"[^a-zA-Z0-9\s]", "", search_term).strip().replace(" ", "-").lower()
    clean_loc = re.sub(r"[^a-zA-Z0-9\s]", "", location).strip().replace(" ", "-").lower()
    if clean_loc in ["remote", "hybrid", ""]:
        url = f"https://www.naukri.com/{clean_keyword}-jobs"
    else:
        url = f"https://www.naukri.com/{clean_keyword}-jobs-in-{clean_loc}"

    logger.info(f"Launching Playwright stealth session for Naukri: {url}")
    jobs: List[DiscoveredJob] = []

    try:
        async with browser_manager.get_page(headless=True) as page:
            success = await browser_manager.safe_goto(page, url, wait_until="domcontentloaded", timeout=25000)
            if not success:
                logger.warning("Could not reach Naukri search URL.")
                return []

            # Realistic human pause
            await browser_manager.random_delay(2.0, 4.0)

            # Smoothly scroll to trigger lazy-loaded listings
            await browser_manager.human_scroll(page, scrolls=3, min_delay=0.8, max_delay=1.5)

            # Select job tuple elements on Naukri
            card_selectors = [
                ".srp-jobtuple-wrapper",
                "article.jobTuple",
                ".cust-job-tuple",
            ]

            card_selector = None
            for sel in card_selectors:
                elements = await page.query_selector_all(sel)
                if elements and len(elements) > 0:
                    card_selector = sel
                    break

            if not card_selector:
                logger.info("No Naukri card selector matched. Page layout may have changed or required captcha.")
                return []

            cards = await page.query_selector_all(card_selector)
            logger.info(f"Found {len(cards)} raw job cards on Naukri.")

            for card in cards[:results_wanted]:
                try:
                    title_elem = await card.query_selector("a.title") or await card.query_selector(".title")
                    title = (await title_elem.inner_text()).strip() if title_elem else ""
                    job_url = await title_elem.get_attribute("href") if title_elem else ""

                    comp_elem = await card.query_selector("a.comp-name") or await card.query_selector(".subTitle")
                    company = (await comp_elem.inner_text()).strip() if comp_elem else ""

                    loc_elem = await card.query_selector(".loc-wrap") or await card.query_selector(".location")
                    loc = (await loc_elem.inner_text()).strip() if loc_elem else location

                    desc_elem = await card.query_selector(".job-desc") or await card.query_selector(".job-description")
                    desc = (await desc_elem.inner_text()).strip() if desc_elem else ""

                    if title and company and job_url:
                        if not job_url.startswith("http"):
                            job_url = "https://www.naukri.com" + job_url

                        jobs.append(
                            DiscoveredJob(
                                title=title,
                                company=company,
                                location=loc,
                                portal="naukri",
                                job_url=job_url,
                                description=desc,
                            )
                        )
                except Exception as card_err:
                    logger.debug(f"Error parsing single Naukri card: {card_err}")
                    continue

        logger.info(f"Playwright extracted {len(jobs)} jobs from Naukri.")
        return jobs

    except Exception as e:
        logger.warning(f"Naukri Playwright scraper encountered exception: {e}")
        return []


async def discover_jobs(
    search_term: Optional[str] = None,
    location: Optional[str] = None,
    portals: Optional[List[str]] = None,
    results_per_portal: int = 10,
    deduplicate: bool = True,
) -> List[DiscoveredJob]:
    """
    High-level orchestrator for job discovery across multiple portals.
    Combines JobSpy (LinkedIn, Indeed, Glassdoor) and Playwright (Naukri).
    Deduplicates against SQLite jobs.db so previously seen jobs are filtered out.
    """
    prefs = load_candidate_preferences()
    target_roles = prefs.get("target_roles", ["Python Developer"])
    preferred_locs = prefs.get("preferred_locations", ["India", "Remote"])

    search = search_term or (target_roles[0] if target_roles else "Python Developer")
    loc = location or (preferred_locs[0] if preferred_locs else "India")
    portal_list = portals or ["naukri"]

    all_jobs: List[DiscoveredJob] = []

    # 1. JobSpy Aggregation (LinkedIn, Indeed, Glassdoor, ZipRecruiter)
    jobspy_portals = [p for p in portal_list if p.lower() in ["linkedin", "indeed", "glassdoor", "zip_recruiter", "ziprecruiter"]]
    if jobspy_portals:
        jobspy_results = await asyncio.to_thread(
            _run_jobspy_sync,
            search_term=search,
            location=loc,
            portals=jobspy_portals,
            results_wanted=results_per_portal,
            country="India" if "india" in loc.lower() else "USA",
        )
        all_jobs.extend(jobspy_results)

    # 2. Playwright Scraping for Naukri if requested
    if "naukri" in [p.lower() for p in portal_list]:
        naukri_results = await scrape_naukri_playwright(
            search_term=search,
            location=loc,
            results_wanted=results_per_portal,
        )
        all_jobs.extend(naukri_results)

    # 3. Deduplication against SQLite Database
    if not deduplicate:
        return all_jobs

    unique_jobs: List[DiscoveredJob] = []
    seen_in_batch = set()

    db = SessionLocal()
    try:
        for job in all_jobs:
            batch_key = (job.title.lower().strip(), job.company.lower().strip())
            if batch_key in seen_in_batch:
                continue

            # Check if this job exists in SQLite database
            exists_in_db = job_exists(db, job_url=job.job_url, title=job.title, company=job.company)
            if exists_in_db:
                logger.debug(f"Skipping duplicate job: {job.title} at {job.company}")
                continue

            seen_in_batch.add(batch_key)
            unique_jobs.append(job)

        logger.info(f"Deduplication complete: {len(unique_jobs)} fresh unique jobs found out of {len(all_jobs)} raw results.")
        return unique_jobs

    finally:
        db.close()
