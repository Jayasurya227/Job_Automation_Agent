"""
Test Suite: test_mailer.py
Validates Sub-Phase 5.4: Account Connection Settings & Recruiter Outreach via Gmail SMTP.
"""
import pytest
from datetime import datetime, timezone
from pathlib import Path
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.agent.mailer import (
    load_account_settings,
    save_account_settings,
    get_masked_settings,
    test_smtp_connection as smtp_connection_validator,
    check_daily_rate_limit,
    send_cold_email,
    AccountSettings,
    SMTPSettings,
    PortalAccountConfig,
)
from app.db.session import init_db
from main import app


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as c:
        yield c


def test_settings_persistence_and_masking():
    """Verify settings save, load, and password masking."""
    settings = AccountSettings(
        smtp=SMTPSettings(
            sender_email="candidate.test@gmail.com",
            sender_name="Jaswanth Test",
            app_password="secretpassword123",
            daily_limit=15,
            enabled=True
        ),
        portals={
            "linkedin": PortalAccountConfig(username="jaswanth_test", password="linkedin_secret_pass", status="connected"),
            "indeed": PortalAccountConfig(username="", password="", status="unconfigured")
        }
    )
    save_account_settings(settings)

    loaded = load_account_settings()
    assert loaded.smtp.sender_email == "candidate.test@gmail.com"
    assert loaded.smtp.daily_limit == 15
    assert loaded.portals["linkedin"].username == "jaswanth_test"

    # Verify password masking
    masked = get_masked_settings()
    assert masked["smtp"]["sender_email"] == "candidate.test@gmail.com"
    assert masked["smtp"]["has_password"] is True
    assert masked["smtp"]["app_password"] != "secretpassword123"
    assert "••••" in masked["smtp"]["app_password"]
    assert masked["portals"]["linkedin"]["has_password"] is True
    assert masked["portals"]["linkedin"]["password"] != "linkedin_secret_pass"
    assert "••••" in masked["portals"]["linkedin"]["password"]


def test_daily_rate_limiting():
    """Verify daily cap prevents sending more than the configured limit."""
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    settings = AccountSettings(
        smtp=SMTPSettings(daily_limit=5),
        emails_sent_today=5,
        last_sent_date=today_str
    )
    allowed, msg = check_daily_rate_limit(settings)
    assert allowed is False
    assert "Daily outreach cap reached" in msg

    # Within limit
    settings.emails_sent_today = 3
    allowed, msg = check_daily_rate_limit(settings)
    assert allowed is True


def test_smtp_connection_validation_with_mock():
    """Verify test_smtp_connection handles successful handshakes and failures."""
    # Test missing credentials
    success, msg = smtp_connection_validator(sender_email="", app_password="")
    assert success is False
    assert "required" in msg.lower()

    # Test with mock SMTP server
    with patch("smtplib.SMTP") as mock_smtp:
        instance = MagicMock()
        mock_smtp.return_value = instance

        success, msg = smtp_connection_validator(
            sender_email="test@gmail.com",
            app_password="abcd efgh ijkl mnop"
        )
        assert success is True
        assert "Successful" in msg
        instance.starttls.assert_called_once()
        instance.login.assert_called_once_with("test@gmail.com", "abcdefghijklmnop")


def test_send_cold_email_with_pdf_attachment():
    """Verify cold email packaging with mock delivery and attachment."""
    # Ensure active settings exist
    save_account_settings(AccountSettings(
        smtp=SMTPSettings(
            sender_email="outreach.sender@gmail.com",
            sender_name="Jaswanth Dev",
            app_password="validmockapppassword",
            daily_limit=10,
            enabled=True
        )
    ))

    # Create a dummy PDF file
    dummy_pdf = Path("output/resumes/test_candidate_resume.pdf")
    dummy_pdf.parent.mkdir(parents=True, exist_ok=True)
    dummy_pdf.write_bytes(b"%PDF-1.4 Mock Candidate Resume Data")

    with patch("smtplib.SMTP") as mock_smtp:
        instance = MagicMock()
        mock_smtp.return_value = instance

        success, msg = send_cold_email(
            recipient_email="recruiter@techcorp.com",
            subject="Application: AI Engineer - Jaswanth",
            body_text="Hi Recruiter, I am reaching out regarding the AI Engineer role...",
            resume_pdf_path=str(dummy_pdf)
        )

        assert success is True
        assert "recruiter@techcorp.com" in msg
        assert "Attached resume" in msg
        instance.sendmail.assert_called_once()

    # Clean up dummy file
    if dummy_pdf.exists():
        dummy_pdf.unlink()


def test_fastapi_settings_and_outreach_endpoints(client):
    """Verify GET /api/settings and PUT /api/settings via FastAPI TestClient."""
    # 1. GET settings
    get_res = client.get("/api/settings")
    assert get_res.status_code == 200
    data = get_res.json()
    assert "smtp" in data
    assert "portals" in data

    # 2. PUT settings update
    update_res = client.put("/api/settings", json={
        "smtp_sender_email": "updated.candidate@gmail.com",
        "smtp_sender_name": "Jaswanth AI",
        "smtp_daily_limit": 12,
        "smtp_enabled": True,
        "portals": {
            "linkedin": {"username": "test_linkedin_user", "password": "new_secret_pwd"}
        }
    })
    assert update_res.status_code == 200
    res_data = update_res.json()
    assert res_data["status"] == "success"
    assert res_data["settings"]["smtp"]["sender_email"] == "updated.candidate@gmail.com"
    assert res_data["settings"]["portals"]["linkedin"]["username"] == "test_linkedin_user"
    assert res_data["settings"]["portals"]["linkedin"]["has_password"] is True


if __name__ == "__main__":
    pytest.main(["-v", __file__])
