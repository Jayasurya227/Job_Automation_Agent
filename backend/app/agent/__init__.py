"""
Agent package for AI intelligence, matching, and automation logic.
"""
from .scorer import analyze_and_score_job
from .tailorer import tailor_resume
from .outreach import generate_outreach
from .browser import BrowserSessionManager, browser_manager
from .scraper import DiscoveredJob, discover_jobs
from .ingestion import IngestionReport, IngestionJobResult, ingest_single_job, discover_and_ingest

__all__ = [
    "analyze_and_score_job",
    "tailor_resume",
    "generate_outreach",
    "BrowserSessionManager",
    "browser_manager",
    "DiscoveredJob",
    "discover_jobs",
    "IngestionReport",
    "IngestionJobResult",
    "ingest_single_job",
    "discover_and_ingest",
]
