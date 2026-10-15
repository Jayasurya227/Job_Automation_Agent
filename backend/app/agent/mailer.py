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
    """
    Validates Gmail SMTP handshake & authentication without sending an email.
    Returns (success: bool, message: str).
    """
    if not sender_email or not app_password:
        return False, "Sender email and Google App Password are required."

    # Strip spaces in app password
    clean_pwd = app_password.replace(" ", "")

    try:
        server = smtplib.SMTP(host, port, timeout=10)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(sender_email.strip(), clean_pwd)
        server.quit()
        return True, "SMTP Authentication Successful! Ready to deliver recruiter outreach."
    except smtplib.SMTPAuthenticationError:
        return False, "Authentication failed. Ensure you are using a 16-character Google App Password (not your normal Gmail password)."
    except Exception as e:
        return False, f"SMTP Connection error: {str(e)}"


def check_daily_rate_limit(settings: AccountSettings) -> Tuple[bool, str]:
    """Ensures outbound outreach adheres to daily safety rate limits (preventing spam flags)."""
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if settings.last_sent_date and settings.last_sent_date != today_str:
        settings.emails_sent_today = 0
        settings.last_sent_date = today_str
        save_account_settings(settings)
    elif settings.last_sent_date is None:
        settings.last_sent_date = today_str

    if settings.emails_sent_today >= settings.smtp.daily_limit:
        return False, f"Daily outreach cap reached ({settings.smtp.daily_limit} emails). Paused to protect email sender reputation."

    return True, "Within daily limit"


def send_cold_email(
    recipient_email: str,
    subject: str,
    body_text: str,
    resume_pdf_path: Optional[str] = None,
    recipient_name: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Sends personalized cold outreach with attached tailored ATS PDF resume via Gmail SMTP.
    Returns (success: bool, details_or_error: str).
    """
    settings = load_account_settings()
    if not settings.smtp.sender_email or not settings.smtp.app_password:
        return False, "Gmail outreach not configured. Please enter your Gmail and App Password in Settings."

    # Check rate limit
    allowed, limit_msg = check_daily_rate_limit(settings)
    if not allowed:
        return False, limit_msg

    # Prepare MIME Message
    msg = MIMEMultipart()
    from_header = f"{settings.smtp.sender_name} <{settings.smtp.sender_email}>" if settings.smtp.sender_name else settings.smtp.sender_email
    msg["From"] = from_header
    msg["To"] = recipient_email.strip()
    msg["Subject"] = subject.strip()
    msg["Date"] = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")

    # Add Body
    msg.attach(MIMEText(body_text.strip(), "plain", "utf-8"))

    # Attach Tailored Resume PDF if available
    attached_name = None
    if resume_pdf_path:
        pdf_file = Path(resume_pdf_path)
        if pdf_file.exists():
            try:
                with open(pdf_file, "rb") as f:
                    part = MIMEApplication(f.read(), _subtype="pdf")
                    filename = pdf_file.name
                    part.add_header("Content-Disposition", "attachment", filename=filename)
                    msg.attach(part)
                    attached_name = filename
            except Exception as att_err:
                logger.warning(f"Could not attach PDF resume ({att_err}). Sending plain email.")

    # Execute Delivery
    clean_pwd = settings.smtp.app_password.replace(" ", "")
    try:
        server = smtplib.SMTP(settings.smtp.host, settings.smtp.port, timeout=15)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(settings.smtp.sender_email.strip(), clean_pwd)
        server.sendmail(settings.smtp.sender_email.strip(), [recipient_email.strip()], msg.as_string())
        server.quit()

        # Update sent counter
        settings.emails_sent_today += 1
        save_account_settings(settings)

        res_msg = f"Email sent successfully to {recipient_email}."
        if attached_name:
            res_msg += f" Attached resume: {attached_name}."
        logger.info(res_msg)
        return True, res_msg
    except Exception as send_err:
        err_msg = f"Delivery failed: {str(send_err)}"
        logger.error(err_msg)
        return False, err_msg
