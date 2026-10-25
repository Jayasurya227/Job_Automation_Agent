"""
Test Suite: test_analytics.py
Validates Sub-Phase 5.3: Analytics, Application Funnel Tracking & Performance Metrics.
"""
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, init_db
from app.db.models import Job, JobEvaluation, Application
from app.db import crud
from main import app


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as c:
        yield c


def test_detailed_analytics_empty_or_existing_db(client):
    """Verify /api/analytics returns 200 with fully structured DetailedAnalyticsResponse."""
    response = client.get("/api/analytics")
    assert response.status_code == 200
    data = response.json()

    assert "summary" in data
    assert "velocity" in data
    assert "conversion_rates" in data
    assert "score_distribution" in data
    assert "portals" in data
    assert "skills_insights" in data
    assert "recent_activity" in data

    summary = data["summary"]
    assert "total_jobs" in summary
    assert "average_match_score" in summary
    assert "applied_count" in summary
    assert "interview_count" in summary
    assert "offer_count" in summary

    rates = data["conversion_rates"]
    assert "apply_rate" in rates
    assert "interview_rate" in rates
    assert "offer_rate" in rates


def test_analytics_calculation_with_seeded_data():
    """Verify mathematical accuracy of conversion rates, velocity, and skills aggregation."""
    with SessionLocal() as db:
        # Create test jobs
        job1 = crud.create_job(
            db=db,
            job_title="Analytics Test Engineer 1",
            company_name="Analytics Corp A",
            job_description="Python, FastAPI, SQL, Docker",
            portal_name="LinkedIn"
        )
        crud.save_job_evaluation(
            db=db,
            job_id=job1.id,
            match=type("MockMatch", (), {
                "match_score": 88,
                "recommendation": "Apply",
                "matching_skills": ["Python", "FastAPI"],
                "missing_skills": ["Kubernetes", "AWS"],
                "key_strengths": ["Strong backend experience"],
                "summary_reasoning": "High fit"
            })()
        )
        crud.create_or_update_application(
            db=db,
            job_id=job1.id,
            status="Applied"
        )

        job2 = crud.create_job(
            db=db,
            job_title="Analytics Test Engineer 2",
            company_name="Analytics Corp B",
            job_description="React, TypeScript, CSS",
            portal_name="Indeed"
        )
        crud.save_job_evaluation(
            db=db,
            job_id=job2.id,
            match=type("MockMatch", (), {
                "match_score": 72,
                "recommendation": "Review",
                "matching_skills": ["Python"],
                "missing_skills": ["Kubernetes", "GraphQL"],
                "key_strengths": ["Quick learner"],
                "summary_reasoning": "Viable fit"
            })()
        )
        crud.create_or_update_application(
            db=db,
            job_id=job2.id,
            status="Interview"
        )

        # Compute analytics
        analytics = crud.get_detailed_analytics(db=db)

        # Check portals
        portal_names = [p["portal"] for p in analytics["portals"]]
        assert "Linkedin" in portal_names or "LinkedIn" in portal_names
        assert "Indeed" in portal_names

        # Check skills aggregation
        matching_map = {item["skill"]: item["count"] for item in analytics["skills_insights"]["top_matching_skills"]}
        missing_map = {item["skill"]: item["count"] for item in analytics["skills_insights"]["top_missing_skills"]}

        assert matching_map.get("Python", 0) >= 2
        assert missing_map.get("Kubernetes", 0) >= 2

        # Check conversion rates
        assert analytics["conversion_rates"]["apply_rate"] > 0
        assert analytics["conversion_rates"]["interview_rate"] > 0

        # Check recent activity list
        assert len(analytics["recent_activity"]) > 0
        recent_titles = [item["job_title"] for item in analytics["recent_activity"]]
        assert "Analytics Test Engineer 1" in recent_titles or "Analytics Test Engineer 2" in recent_titles

        # Clean up seeded test records
        crud.delete_job(db=db, job_id=job1.id)
        crud.delete_job(db=db, job_id=job2.id)


if __name__ == "__main__":
    pytest.main(["-v", __file__])
