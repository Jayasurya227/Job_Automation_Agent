"""
Autonomous Multi-Portal Job Scraper & Discovery Engine.
Integrates JobSpy high-speed aggregation with Playwright stealth browser extraction.
Supports LinkedIn, Indeed, Naukri, Glassdoor, and ZipRecruiter.
Includes smart deduplication against SQLite jobs.db and anti-bot pacing.
Part of Phase 3: Browser Automation & Job Discovery.
"""

import re
import sys
import time
import json
import random
import logging
import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from pydantic import BaseModel, Field

# Ensure Windows ProactorEventLoop is used so Playwright child processes don't raise NotImplementedError
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass

from app.agent.browser import browser_manager
from app.db.session import SessionLocal
from app.db.crud import job_exists
from app.utils.event_bus import emit_event

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
    apply_type: str = Field(default="1-Click", description="Application type: '1-Click' or 'External'")
    external_url: Optional[str] = Field(default=None, description="Direct employer ATS link if external")


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


def is_title_relevant(job_title: str, target_roles: List[str]) -> bool:
    """
    Strict Title-Related Filter (Step 1):
    Ensures scraped job titles belong to the candidate's target career domains.
    Eliminates unrelated keyword-stuffed jobs (e.g. Cyber Security with Python, PowerBI with Python, Tech Support).
    """
    if not job_title or not job_title.strip():
        return False

    title_lower = job_title.lower().strip()

    normalized_targets = [r.lower().strip() for r in target_roles if r.strip()]
    if not normalized_targets:
        return True

    # 1. Negative Patterns: Non-engineering or unrelated career tracks
    negative_patterns = [
        (["cyber", "security", "soc analyst", "infosec", "penetration tester"], "cyber security"),
        (["power bi", "powerbi", "tableau", "qlik", "business intelligence"], "bi/reporting"),
        (["technical support", "desktop support", "it support", "helpdesk", "service desk", "customer care", "bpo", "telecaller", "call center", "voice process"], "support"),
        (["sales", "business development", "bde", "inside sales", "telemarketing", "digital marketing", "seo executive", "seo analyst"], "sales & marketing"),
        (["recruiter", "talent acquisition", "hr executive", "hr generalist"], "hr"),
        (["data entry", "back office", "computer operator"], "data entry"),
        (["manual tester", "manual qa", "manual testing"], "manual testing"),
        (["hardware engineer", "network administrator", "desktop engineer", "system administrator"], "hardware/sysadmin"),
    ]

    for keywords, category in negative_patterns:
        user_wants_category = any(
            any(kw in target for kw in keywords) for target in normalized_targets
        )
        if not user_wants_category:
            for kw in keywords:
                if re.search(r'\b' + re.escape(kw) + r'\b', title_lower):
                    logger.info(f"🚫 Title Filter DROPPED unrelated '{job_title}' (Matched negative keyword: '{kw}')")
                    return False

    # 2. Positive Match: Title must belong to candidate's target roles / career tracks
    for target in normalized_targets:
        if target in title_lower:
            return True

    # Skill/Domain tokens derived from target roles
    domain_tokens = set()
    for target in normalized_targets:
        if "ai" in target.split() or "genai" in target or "gen ai" in target:
            domain_tokens.update(["ai", "artificial intelligence", "genai", "generative ai", "llm", "deep learning", "nlp"])
        if "ml" in target.split() or "machine learning" in target:
            domain_tokens.update(["ml", "machine learning", "data scientist"])
        if "python" in target:
            domain_tokens.update(["python", "django", "fastapi", "flask", "backend"])
        if "full stack" in target or "fullstack" in target:
            domain_tokens.update(["full stack", "fullstack", "frontend", "backend", "mern", "mean", "web developer"])
        
        words = re.findall(r'[a-zA-Z0-9]+', target)
        for w in words:
            if len(w) > 2 and w not in ["engineer", "developer", "fresher", "intern", "junior", "lead", "specialist", "associate"]:
                domain_tokens.add(w)

    dev_words = ["developer", "engineer", "sde", "programmer", "architect", "analyst"]

    has_domain_token = any(re.search(r'\b' + re.escape(tok) + r'\b', title_lower) for tok in domain_tokens)
    has_dev_word = any(re.search(r'\b' + re.escape(dw) + r'\b', title_lower) for dw in dev_words)

    if has_domain_token:
        return True

    is_software_target = any(
        any(sw in target for sw in ["developer", "software", "engineer", "full stack", "backend", "python"])
        for target in normalized_targets
    )
    if is_software_target and ("software engineer" in title_lower or "software developer" in title_lower or "sde" in title_lower or "backend" in title_lower):
        return True

    logger.info(f"🚫 Title Filter DROPPED non-matching title '{job_title}' (Does not match target roles: {normalized_targets})")
    return False


def _run_jobspy_sync(
    search_term: str,
    location: str,
    portals: List[str],
    results_wanted: int,
    country: str,
    hours_old: int = 72,
    experience_level: Optional[str] = None,
    target_roles: Optional[List[str]] = None,
) -> List[DiscoveredJob]:
    """
    Synchronous wrapper to execute JobSpy scrape_jobs safely inside a worker thread.
    Enhanced for Indeed & multi-portal discovery with Indian geo-routing and entry-level guards.
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
        valid_sites = ["indeed"]

    # Intelligent Indian geo-routing and location normalization for Indeed
    loc_clean = location.strip()
    loc_lower = loc_clean.lower()
    if loc_lower in ["hybrid", "remote", "any", "all", "", "india"]:
        effective_location = "India"
        country_indeed = "India"
    else:
        effective_location = loc_clean
        indian_cities = [
            "hyderabad", "bengaluru", "bangalore", "pune", "mumbai",
            "delhi", "noida", "gurgaon", "gurugram", "chennai",
            "kolkata", "ahmedabad"
        ]
        is_india = any(c in loc_lower for c in indian_cities) or country.lower() == "india"
        country_indeed = "India" if is_india else "USA"

    # Robust batch size: Request at least 15 jobs so Indeed returns a full page rather than sponsored crumbs
    target_results = max(15, min(results_wanted, 25))

    try:
        logger.info(f"Running JobSpy for '{search_term}' in '{effective_location}' across {valid_sites} (target: {target_results}, country: {country_indeed}, exp: {experience_level})...")
        df = scrape_jobs(
            site_name=valid_sites,
            search_term=search_term,
            location=effective_location,
            results_wanted=target_results,
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
            raw_site = str(row.get("site", "") or "Indeed").strip()
            # Normalize portal branding display
            site = "Indeed" if raw_site.lower() == "indeed" else raw_site.title()

            # Strict Title-Related Relevance Filter (Step 1)
            effective_roles = target_roles or [search_term]
            if not is_title_relevant(title, effective_roles):
                continue

            # Upfront Expiry Filter: Drop expired / closed listings immediately
            desc_lower = (desc or "").lower()
            is_job_expired = bool(
                row.get("is_closed") is True or
                "this job has expired" in desc_lower or
                "job is no longer available" in desc_lower or
                "this job is no longer accepting applications" in desc_lower or
                "position has been filled" in desc_lower or
                "this vacancy has expired" in desc_lower or
                "job has been closed by employer" in desc_lower or
                "this job posting has expired" in desc_lower
            )
            if is_job_expired:
                logger.info(f"🚫 EXPIRED JOB FILTERED on {site}: '{title}' at '{company}' is expired/closed. Dropping upfront!")
                continue

            # Entry-level / fresher guard for 0-1 years target
            if experience_level in ["0-1", "0"]:
                title_lower = title.lower()
                senior_markers = [
                    "senior", "sr.", "sr ", "lead", "principal", "architect",
                    "manager", "director", "head of", "5+ years", "6+ years",
                    "7+ years", "8+ years", "10+ years"
                ]
                if any(m in title_lower for m in senior_markers):
                    logger.debug(f"Skipping senior {site} listing: '{title}' at '{company}'")
                    continue

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

            # Detect Apply Type: If JobSpy provides an external direct recruiter/ATS URL, it is an External company portal
            job_url_direct = str(row.get("job_url_direct", "") or "").strip()
            is_external = bool(
                job_url_direct and 
                job_url_direct.lower() not in ["none", "nan", ""] and 
                "indeed.com" not in job_url_direct.lower()
            )
            apply_type = "External" if is_external else "1-Click"
            target_job_url = job_url_direct if (is_external and job_url_direct.startswith("http")) else job_url

            if title and company and job_url:
                discovered.append(
                    DiscoveredJob(
                        title=title,
                        company=company,
                        location=loc or location,
                        portal=site,
                        job_url=target_job_url or job_url,
                        description=desc,
                        salary=salary_str,
                        date_posted=date_posted,
                        apply_type=apply_type,
                        external_url=job_url_direct if is_external else None,
                    )
                )

        logger.info(f"JobSpy successfully extracted {len(discovered)} qualified fresh listings.")
        return discovered

    except Exception as e:
        logger.error(f"JobSpy scraping error: {e}", exc_info=True)
        return []


def _fetch_naukri_full_description_sync(page, job_url: str, fallback_desc: str = "") -> Tuple[str, str, bool, bool]:
    """
    Synchronously and stealthily navigates to a Naukri job URL to extract:
    1. The complete, official job description
    2. Upfront Apply Type ('1-Click' vs 'External')
    3. Whether candidate has already applied to this posting
    4. Whether job has expired / closed
    Uses multi-selector fallbacks and a 12s timeout to prevent stalls.
    """
    if not job_url or not job_url.startswith("http"):
        return fallback_desc, "1-Click", False, False

    try:
        page.goto(job_url, wait_until="domcontentloaded", timeout=12000)
        time.sleep(random.uniform(0.8, 1.4))

        body_text = page.inner_text("body") or ""
        body_lower = body_text.lower()

        # 0. Upfront Expiry Detection: Instantly drop expired Naukri listings
        is_expired = bool(
            page.query_selector(
                ".expired-job, .job-expired, .expired-banner, [class*='expired'], "
                "div:has-text('This job has expired'), span:has-text('This job has expired'), "
                "div:has-text('Job has expired'), span:has-text('Job has expired'), "
                "div:has-text('This job is no longer active')"
            ) or
            "this job has expired" in body_lower or
            "this job is no longer active" in body_lower or
            "job has expired" in body_lower or
            "this vacancy has expired" in body_lower or
            "this vacancy has been filled" in body_lower or
            "you can find similar jobs below" in body_lower or
            "the job you are looking for is no longer available" in body_lower or
            "we are no longer accepting responses" in body_lower
        )
        if is_expired:
            logger.info(f"🚫 EXPIRED JOB on Naukri: {job_url}. Marking as expired.")
            return "", "1-Click", False, True

        # 1. Detect if candidate already applied on Naukri
        is_already_applied = False
        if page.query_selector(".already-applied, span:has-text('Applied'):visible, div.applied-text"):
            is_already_applied = True
        elif "\nApplied\n" in body_text or "\nAlready applied\n" in body_text:
            is_already_applied = True

        # 2. Detect Apply Type: External Company Portal vs 1-Click
        ext_btn = page.query_selector(
            "button:has-text('Apply on company site'), "
            "a:has-text('Apply on company site'), "
            ".company-site-button, "
            "[class*='apply-type-external'], "
            "a:has-text('Apply on employer website')"
        )
        is_external = bool(
            (ext_btn and ext_btn.is_visible()) or
            "aggregated from external source" in body_text.lower() or
            ("naukri.com" not in page.url.lower())
        )
        apply_type = "External" if is_external else "1-Click"

        jd_selectors = [
            ".styles_JDJD__xx",
            "[class*='styles_JDJD']",
            ".dang-inner-html",
            "section.job-desc-wrapper",
            ".job-desc-wrapper",
            "[class*='job-desc']",
            "article",
            "main",
        ]

        full_text = ""
        for sel in jd_selectors:
            elem = page.query_selector(sel)
            if elem:
                txt = elem.inner_text().strip()
                if len(txt) > len(full_text):
                    full_text = txt
                if len(full_text) > 250:
                    break

        if full_text and len(full_text) > len(fallback_desc):
            cleaned = re.sub(r'\n\s*\n', '\n\n', full_text).strip()
            return cleaned, apply_type, is_already_applied, False

        return fallback_desc, apply_type, is_already_applied, False
    except Exception as e:
        logger.debug(f"Full JD sync fetch notice on {job_url}: {e}")
        return fallback_desc, "1-Click", False, False


def _scrape_naukri_sync(
    search_term: str,
    location: str = "India",
    results_wanted: int = 10,
    freshness_days: int = 1,
    experience_level: Optional[str] = None,
    target_roles: Optional[List[str]] = None,
) -> List[DiscoveredJob]:
    """
    Production-Standard Synchronous Stealth Scraper for Naukri.com.
    Runs inside a dedicated worker thread (asyncio.to_thread) to completely bypass
    Windows event loop conflicts (NotImplementedError in Uvicorn).
    Uses installed Google Chrome (channel='chrome') + user session cookies + stealth flags
    to safely bypass Akamai bot protection and reliably extract fresh job listings.
    """
    from playwright.sync_api import sync_playwright
    from app.agent.browser import DEFAULT_SESSION_DIR, sanitize_session_preferences, DEFAULT_USER_AGENT
    from app.agent.stealth import get_stealth_chromium_args, build_stealth_js, check_bot_challenge

    # Clean keyword and location for URL
    clean_keyword = re.sub(r"[^a-zA-Z0-9\s]", "", search_term).strip().replace(" ", "-").lower()
    clean_loc = re.sub(r"[^a-zA-Z0-9\s]", "", location).strip().replace(" ", "-").lower()
    if clean_loc in ["remote", "hybrid", "india", ""]:
        base_url = f"https://www.naukri.com/{clean_keyword}-jobs"
    else:
        base_url = f"https://www.naukri.com/{clean_keyword}-jobs-in-{clean_loc}"

    # Determine effective experience filter from profile if not provided
    if experience_level is None:
        prefs = load_candidate_preferences()
        experience_level = prefs.get("experience_level", "0-1")

    # Build query parameters (freshness + experience filters)
    params = []
    if freshness_days and freshness_days > 0:
        params.append(f"freshness={freshness_days}")

    if experience_level == "0-1":
        params.extend(["experience=0", "experience=1"])
    elif experience_level == "1-2":
        params.extend(["experience=1", "experience=2"])
    elif experience_level == "2-4":
        params.extend(["experience=2", "experience=3", "experience=4"])
    elif experience_level == "0":
        params.append("experience=0")

    query_str = f"?{'&'.join(params)}" if params else ""
    url = f"{base_url}{query_str}"

    session_dir = Path(DEFAULT_SESSION_DIR)
    session_dir.mkdir(parents=True, exist_ok=True)
    sanitize_session_preferences(session_dir)

    launch_args = list(get_stealth_chromium_args())
    launch_args.extend([
        "--window-position=-2400,-2400",
        "--window-size=1280,800",
        "--no-first-run",
        "--no-default-browser-check",
    ])

    launch_kwargs: Dict[str, Any] = {
        "user_data_dir": str(session_dir),
        "headless": True,
        "args": launch_args,
        "user_agent": DEFAULT_USER_AGENT,
        "viewport": {"width": 1280, "height": 800},
        "locale": "en-US",
        "timezone_id": "Asia/Kolkata",
        "ignore_https_errors": True,
    }

    logger.info(f"Launching Naukri sync worker thread (channel='chrome', freshness={freshness_days}d, exp={experience_level}): {url}")
    raw_jobs: List[DiscoveredJob] = []

    p = None
    context = None
    try:
        p = sync_playwright().start()
        # Attempt channel='chrome' or channel='msedge' to bypass Akamai bot firewall
        for ch in ["chrome", "msedge", None]:
            try:
                kw = dict(launch_kwargs)
                if ch:
                    kw["channel"] = ch
                context = p.chromium.launch_persistent_context(**kw)
                break
            except Exception as e:
                logger.debug(f"Could not launch channel={ch}: {e}")
        if context is None:
            context = p.chromium.launch_persistent_context(**launch_kwargs)

        context.add_init_script(build_stealth_js())
        page = context.pages[0] if context.pages else context.new_page()

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception as goto_err:
            logger.warning(f"Could not reach Naukri search URL: {goto_err}")
            return []

        # Human-like pause and lazy-load scroll
        time.sleep(random.uniform(2.0, 3.5))
        for _ in range(3):
            page.mouse.wheel(0, 700)
            time.sleep(random.uniform(0.8, 1.4))

        # Check bot challenge
        challenge = check_bot_challenge(page)
        if challenge:
            logger.warning(f"Naukri bot challenge detected on search listing: {challenge}")

        card_selectors = [
            ".srp-jobtuple-wrapper",
            "article.jobTuple",
            ".cust-job-tuple",
            "[class*='srp-jobtuple']",
        ]

        card_selector = None
        for sel in card_selectors:
            elements = page.query_selector_all(sel)
            if elements and len(elements) > 0:
                card_selector = sel
                break

        if not card_selector:
            logger.info("No Naukri card selector matched. Page layout may have changed or required captcha.")
            return []

        cards = page.query_selector_all(card_selector)
        logger.info(f"Found {len(cards)} raw job cards on Naukri.")

        effective_roles = target_roles or [search_term]

        for card in cards[: max(results_wanted * 2, 15)]:
            try:
                title_elem = card.query_selector("a.title") or card.query_selector(".title")
                title = title_elem.inner_text().strip() if title_elem else ""
                job_url = title_elem.get_attribute("href") if title_elem else ""

                # Strict Title-Related Relevance Filter (Step 1)
                if not is_title_relevant(title, effective_roles):
                    continue

                comp_elem = card.query_selector("a.comp-name") or card.query_selector(".subTitle") or card.query_selector("[class*='comp-name']")
                company = comp_elem.inner_text().strip() if comp_elem else ""

                loc_elem = card.query_selector(".loc-wrap") or card.query_selector(".location") or card.query_selector("[class*='loc-wrap']")
                loc = loc_elem.inner_text().strip() if loc_elem else location

                desc_elem = card.query_selector(".job-desc") or card.query_selector(".job-description") or card.query_selector("[class*='job-desc']")
                desc = desc_elem.inner_text().strip() if desc_elem else ""

                sal_elem = card.query_selector(".sal-wrap") or card.query_selector(".salary") or card.query_selector("[class*='sal-wrap']")
                salary_str = sal_elem.inner_text().strip() if sal_elem else ""

                date_elem = (
                    card.query_selector(".job-post-day") or
                    card.query_selector("span.date") or
                    card.query_selector(".type") or
                    card.query_selector(".tuple-sub-title")
                )
                date_posted = date_elem.inner_text().strip() if date_elem else "Past 24 Hours"

                exp_elem = (
                    card.query_selector(".exp-wrap") or
                    card.query_selector("span.expwdth") or
                    card.query_selector(".experience")
                )
                card_exp = exp_elem.inner_text().strip() if exp_elem else ""

                if experience_level in ["0-1", "0"] and card_exp:
                    senior_match = re.search(r"\b([3-9]|\d{2})\s*-\s*\d+\s*(?:Yrs|Years?)", card_exp, re.IGNORECASE)
                    if senior_match:
                        logger.debug(f"Skipping senior job card '{title}' requiring '{card_exp}'")
                        continue

                if title and company and job_url:
                    if not job_url.startswith("http"):
                        job_url = "https://www.naukri.com" + job_url

                    raw_jobs.append(
                        DiscoveredJob(
                            title=title,
                            company=company,
                            location=loc,
                            portal="naukri",
                            job_url=job_url,
                            description=desc,
                            salary=salary_str,
                            date_posted=date_posted,
                        )
                    )
            except Exception as card_err:
                logger.debug(f"Error parsing single Naukri card: {card_err}")
                continue

        # Step 1: Filter out duplicates against SQLite so we only deep-fetch brand new jobs
        db = SessionLocal()
        fresh_jobs = []
        try:
            for j in raw_jobs:
                if not job_exists(db, job_url=j.job_url, title=j.title, company=j.company):
                    fresh_jobs.append(j)
                else:
                    logger.debug(f"Skipping known job: {j.title} at {j.company}")
        finally:
            db.close()

        jobs_to_process = fresh_jobs[:results_wanted] if fresh_jobs else raw_jobs[:results_wanted]

        # Step 2: Deep Extraction - Visit each fresh job page to pull 100% full official description
        logger.info(f"Initiating deep full-page JD extraction for {len(jobs_to_process)} fresh jobs...")
        valid_active_jobs = []
        for idx, job in enumerate(jobs_to_process):
            try:
                emit_event("discovery", "discovery_progress", {
                    "stage": "deep_fetch",
                    "title": job.title,
                    "company": job.company,
                    "current": idx + 1,
                    "total": len(jobs_to_process),
                    "message": f"Extracting 100% full job description for '{job.title}' at {job.company} ({idx+1}/{len(jobs_to_process)})..."
                })
                full_jd, apply_type, is_already_applied, is_expired = _fetch_naukri_full_description_sync(page, job.job_url, fallback_desc=job.description)

                if is_expired:
                    logger.info(f"🚫 EXPIRED JOB FILTERED: '{job.title}' at '{job.company}' is expired on Naukri. Skipping immediately!")
                    emit_event("discovery", "discovery_progress", {
                        "stage": "expired_skip",
                        "title": job.title,
                        "company": job.company,
                        "portal": "naukri",
                        "message": f"🚫 Skipped expired job: '{job.title}' at {job.company}"
                    })
                    continue

                if full_jd and len(full_jd) > len(job.description):
                    job.description = full_jd
                if is_already_applied:
                    job.apply_type = "Applied"
                else:
                    job.apply_type = apply_type

                valid_active_jobs.append(job)

                if idx < len(jobs_to_process) - 1:
                    time.sleep(random.uniform(1.0, 1.8))
            except Exception as jd_err:
                logger.warning(f"Error fetching full JD for '{job.title}': {jd_err}")
                continue

        logger.info(f"Naukri sync worker successfully extracted {len(valid_active_jobs)} active full-detail jobs.")
        return valid_active_jobs

    except Exception as e:
        logger.warning(f"Naukri sync scraper encountered exception: {e}")
        return []
    finally:
        if context:
            try:
                context.close()
            except Exception:
                pass
        if p:
            try:
                p.stop()
            except Exception:
                pass
        sanitize_session_preferences(session_dir)


async def scrape_naukri_playwright(
    search_term: str,
    location: str = "India",
    results_wanted: int = 10,
    freshness_days: int = 1,
    experience_level: Optional[str] = None,
    target_roles: Optional[List[str]] = None,
) -> List[DiscoveredJob]:
    """
    Async interface for the Naukri stealth scraper.
    Delegates execution to _scrape_naukri_sync in a dedicated worker thread
    to guarantee 100% Windows event-loop isolation and zero NotImplementedError crashes.
    """
    return await asyncio.to_thread(
        _scrape_naukri_sync,
        search_term=search_term,
        location=location,
        results_wanted=results_wanted,
        freshness_days=freshness_days,
        experience_level=experience_level,
        target_roles=target_roles,
    )


async def discover_jobs(
    search_term: Optional[str] = None,
    search_terms: Optional[List[str]] = None,
    location: Optional[str] = None,
    locations: Optional[List[str]] = None,
    portals: Optional[List[str]] = None,
    results_per_portal: int = 10,
    freshness_days: int = 1,
    experience_level: Optional[str] = None,
    deduplicate: bool = True,
) -> List[DiscoveredJob]:
    """
    High-level orchestrator for job discovery across multiple portals.
    Supports dynamic multi-role and multi-location scanning based on user's saved preferences.
    Combines JobSpy (LinkedIn, Indeed, Glassdoor) and Playwright (Naukri).
    Deduplicates against SQLite jobs.db so previously seen jobs are filtered out.
    """
    prefs = load_candidate_preferences()
    saved_roles = prefs.get("target_roles", [])
    preferred_locs = prefs.get("preferred_locations", ["Hyderabad", "Bengaluru"])
    saved_freshness = prefs.get("freshness_days", 1)
    saved_exp = prefs.get("experience_level", "0-1")
    effective_exp = experience_level if experience_level is not None else saved_exp

    # 1. Determine roles to search dynamically based on saved preferences
    if search_terms and len(search_terms) > 0:
        roles_to_search = [r.strip() for r in search_terms if r and r.strip()]
    elif search_term and search_term.strip():
        if "," in search_term:
            roles_to_search = [r.strip() for r in search_term.split(",") if r and r.strip()]
        else:
            roles_to_search = [search_term.strip()]
    elif saved_roles:
        roles_to_search = [r.strip() for r in saved_roles if r and r.strip()]
    else:
        roles_to_search = ["Junior AI Engineer"]

    # Cap to top 3 roles per discovery cycle for bot safety & human pacing
    roles_to_search = roles_to_search[:3]

    # 2. Determine locations to search dynamically based on saved preferences
    if locations and len(locations) > 0:
        locs_to_search = [l.strip() for l in locations if l and l.strip()]
    elif location and location.strip():
        if "," in location:
            locs_to_search = [l.strip() for l in location.split(",") if l and l.strip()]
        else:
            locs_to_search = [location.strip()]
    elif preferred_locs:
        # Take up to top 2 active preferred locations (e.g. Hyderabad, Bengaluru)
        locs_to_search = [l.strip() for l in preferred_locs if l and l.strip()]
    else:
        locs_to_search = ["Hyderabad"]

    # Prioritize real metropolitan hubs over work modes like "Hybrid" or "Remote"
    real_cities = [l for l in locs_to_search if l.lower() not in ["hybrid", "remote", "onsite", "any"]]
    if real_cities:
        locs_to_search = real_cities[:2]
    else:
        locs_to_search = locs_to_search[:2]

    portal_list = portals or ["naukri"]
    effective_freshness = freshness_days if freshness_days is not None else saved_freshness

    # Generate balanced search pairs (e.g. (Role, Location)) capped to top 2 queries for high speed
    search_pairs = [(r, l) for r in roles_to_search for l in locs_to_search]
    if len(search_pairs) > 2:
        search_pairs = search_pairs[:2]

    # Guarantee healthy volume per query (15-20 jobs) rather than dividing down to crumbs
    per_query_results = max(15, results_per_portal)

    all_jobs: List[DiscoveredJob] = []

    for pair_idx, (current_role, current_loc) in enumerate(search_pairs):
        if pair_idx > 0:
            # Human-like delay between searching different queries
            await asyncio.sleep(2.0)

        logger.info(f"Scanning portals in parallel for [{pair_idx+1}/{len(search_pairs)}]: '{current_role}' in '{current_loc}'...")

        # Concurrent parallel crawl tasks for current search pair
        crawl_tasks = []
        task_names = []

        # 1. JobSpy Aggregation (Indeed, LinkedIn, Glassdoor, ZipRecruiter)
        jobspy_portals = [p for p in portal_list if p.lower() in ["linkedin", "indeed", "glassdoor", "zip_recruiter", "ziprecruiter"]]
        if jobspy_portals:
            if effective_freshness is not None and int(effective_freshness) == 0:
                hours_old = None  # All time / No 24-hour limit
            elif effective_freshness and int(effective_freshness) > 0:
                hours_old = int(effective_freshness) * 24
            else:
                hours_old = 24  # Default to 24h only if freshness omitted
            indian_cities = [
                "hyderabad", "bengaluru", "bangalore", "pune", "mumbai",
                "delhi", "noida", "gurgaon", "gurugram", "chennai",
                "kolkata", "ahmedabad", "remote", "india"
            ]
            is_india_loc = any(c in current_loc.lower() for c in indian_cities)
            country_target = "India" if is_india_loc else "USA"

            crawl_tasks.append(asyncio.to_thread(
                _run_jobspy_sync,
                search_term=current_role,
                location=current_loc,
                portals=jobspy_portals,
                results_wanted=per_query_results,
                country=country_target,
                hours_old=hours_old,
                experience_level=effective_exp,
                target_roles=roles_to_search,
            ))
            task_names.append("Indeed/JobSpy")

        # 2. Playwright Scraping for Naukri if requested
        if "naukri" in [p.lower() for p in portal_list]:
            crawl_tasks.append(scrape_naukri_playwright(
                search_term=current_role,
                location=current_loc,
                results_wanted=per_query_results,
                freshness_days=effective_freshness,
                experience_level=effective_exp,
                target_roles=roles_to_search,
            ))
            task_names.append("Naukri")

        # Execute parallel crawls simultaneously
        if crawl_tasks:
            results = await asyncio.gather(*crawl_tasks, return_exceptions=True)
            for name, res in zip(task_names, results):
                if isinstance(res, Exception):
                    logger.warning(f"Error crawling {name}: {res}")
                elif isinstance(res, list):
                    all_jobs.extend(res)

    # Strict Title-Related Relevance Filter (Step 1)
    all_jobs = [j for j in all_jobs if is_title_relevant(j.title, roles_to_search)]

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
