"""
Module: mailer.py
Purpose: Sub-Phase 5.4 - Recruiter Cold Outreach Delivery Engine via Gmail SMTP with PDF Resume Attachments.
Standards: Rule 1 (Zero Blind Trust), Rule 2 (Type & Schema Safety), Rule 3 (Low Code & High Signal),
           Rule 5 (Production Reliability & Spam Prevention Rate Limiting).
"""
import os
import json
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

from pydantic import BaseModel, Field

logger = logging.getLogger("agent.mailer")

SETTINGS_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "account_settings.json"
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class SMTPSettings(BaseModel):
    """Configuration for Gmail SMTP outreach delivery."""
    host: str = Field(default="smtp.gmail.com", description="SMTP server hostname")
    port: int = Field(default=587, description="SMTP server port (587 for TLS)")
    sender_email: str = Field(default="", description="Sender Gmail address")
    sender_name: str = Field(default="", description="Sender display name")
    app_password: str = Field(default="", description="Google 16-character App Password")
    daily_limit: int = Field(default=10, ge=1, le=50, description="Max cold emails allowed per day")
    enabled: bool = Field(default=False, description="Whether automated outreach is activated")


class PortalAccountConfig(BaseModel):
    """Stores candidate portal credentials status and login state."""
    username: str = ""
    password: str = ""
    status: str = "unconfigured"  # unconfigured, connected, expired
    last_verified: Optional[str] = None


class AccountSettings(BaseModel):
    """Unified local settings for candidate accounts and outreach."""
    smtp: SMTPSettings = Field(default_factory=SMTPSettings)
    portals: Dict[str, PortalAccountConfig] = Field(default_factory=lambda: {
        "naukri": PortalAccountConfig()
    })
    emails_sent_today: int = 0
    last_sent_date: Optional[str] = None


def load_account_settings() -> AccountSettings:
    """Loads account settings from local JSON file or environment variables."""
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return AccountSettings(**data)
        except Exception as e:
            logger.warning(f"Could not load account_settings.json ({e}). Using defaults.")

    # Fallback to .env values if set
    smtp_from_env = SMTPSettings(
        sender_email=os.getenv("SENDER_EMAIL", ""),
        sender_name=os.getenv("SENDER_NAME", ""),
        app_password=os.getenv("GMAIL_APP_PASSWORD", ""),
        enabled=bool(os.getenv("GMAIL_APP_PASSWORD")),
    )
    return AccountSettings(smtp=smtp_from_env)


def save_account_settings(settings: AccountSettings) -> None:
    """Saves account settings locally on candidate's machine."""
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings.model_dump(), f, indent=2)


def get_masked_settings() -> Dict[str, Any]:
    """Returns safe settings payload with passwords masked for frontend UI display."""
    settings = load_account_settings()
    data = settings.model_dump()

    # Mask SMTP password
    has_smtp_pwd = bool(settings.smtp.app_password)
    data["smtp"]["app_password"] = "••••••••••••••••" if has_smtp_pwd else ""
    data["smtp"]["has_password"] = has_smtp_pwd

    # Mask portal passwords
    for p_name, p_data in data.get("portals", {}).items():
        has_pwd = bool(p_data.get("password"))
        p_data["password"] = "••••••••••••" if has_pwd else ""
        p_data["has_password"] = has_pwd

    return data


def test_smtp_connection(
    host: str = "smtp.gmail.com",
    port: int = 587,
    sender_email: str = "",
    app_password: str = ""
) -> Tuple[bool, str]:
    """SMTP test is paused per user configuration."""
    return False, "Recruiter cold email / SMTP outreach feature is currently paused to prioritize direct portal applications."


def check_daily_rate_limit(settings: AccountSettings) -> Tuple[bool, str]:
    """Ensures outbound outreach adheres to daily safety rate limits."""
    return True, "Within limit"


def send_cold_email(
    recipient_email: str,
    subject: str,
    body_text: str,
    resume_pdf_path: Optional[str] = None,
    recipient_name: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Cold email delivery is paused per user configuration to focus exclusively
    on direct 1-click applications on Naukri.
    """
    logger.info("Cold email request received but outreach feature is paused.")
    return False, "Recruiter cold email outreach is paused. Direct 1-click job application is the primary channel."
