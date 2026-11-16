"""
Module: auth.py
Purpose: FastAPI router for user registration, authentication, token resolution, profile inspection,
         and secure 6-digit OTP password recovery.
Standards: Rule 1 (Zero Vulnerability), Rule 2 (Strict Type & Schema Validation), Rule 5 (Production Reliability).
"""
import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import OTP_EXPIRE_MINUTES
from app.db.session import get_db
from app.db.models import User, PasswordResetOTP
from app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    UserResponse,
    TokenResponse,
    ForgotPasswordRequest,
    VerifyOTPResetPasswordRequest,
    VerifyOTPOnlyRequest,
    VerifyOTPOnlyResponse,
    SetNewPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordResponse,
)
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    get_current_user,
    generate_cryptographic_otp,
)

logger = logging.getLogger("router.auth")

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account"
)
def register_user(
    payload: UserRegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Registers a new candidate user account with full name, email, and password.
    Returns signed JWT access token and user profile upon success.
    """
    clean_email = payload.email.strip().lower()
    clean_name = payload.full_name.strip()

    # 1. Check for existing email registration
    existing_user = db.query(User).filter(User.email == clean_email).first()
    if existing_user:
        logger.warning(f"Registration rejected: Email '{clean_email}' already in use.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists. Please sign in or reset your password."
        )

    # 2. Hash password with bcrypt
    hashed_pw = hash_password(payload.password)

    # 3. Persist new user
    new_user = User(
        full_name=clean_name,
        email=clean_email,
        password_hash=hashed_pw,
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    logger.info(f"New user registered successfully: User #{new_user.id} ({new_user.email})")

    # 4. Generate JWT access token
    token = create_access_token(user_id=new_user.id, email=new_user.email)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(new_user)
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate user and issue JWT access token"
)
def login_user(
    payload: UserLoginRequest,
    db: Session = Depends(get_db)
):
    """
    Authenticates candidate with email and password.
    Returns 7-day signed JWT access token.
    """
    clean_email = payload.email.strip().lower()

    # 1. Lookup user by email
    user = db.query(User).filter(User.email == clean_email).first()
    if not user:
        logger.warning(f"Login failed: Email not found '{clean_email}'.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password. Please verify your credentials.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # 2. Verify password with bcrypt (constant-time safe)
    if not verify_password(payload.password, user.password_hash):
        logger.warning(f"Login failed: Invalid password for '{clean_email}'.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password. Please verify your credentials.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # 3. Check active status
    if not user.is_active:
        logger.warning(f"Login blocked: Inactive account for '{clean_email}'.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated. Please contact support."
        )

    logger.info(f"User logged in successfully: User #{user.id} ({user.email})")

    # 4. Issue JWT access token
    token = create_access_token(user_id=user.id, email=user.email)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated user profile"
)
def get_me(
    current_user: User = Depends(get_current_user)
):
    """
    Returns the profile of the currently logged-in user from Bearer JWT token.
    Used by frontend on mount/refresh to restore session state.
    """
    return UserResponse.model_validate(current_user)


def dispatch_otp_email(to_email: str, recipient_name: str, otp_code: str) -> bool:
    """Attempts to dispatch OTP via configured SMTP; logs on success or gracefully logs fallback."""
    import os
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    # Read credentials from environment or account_settings.json
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "") or os.getenv("SMTP_PASS", "")

    if not smtp_user or not smtp_password:
        try:
            from app.agent.mailer import load_account_settings
            settings = load_account_settings()
            if settings.smtp.sender_email and settings.smtp.app_password:
                smtp_host = settings.smtp.host
                smtp_port = settings.smtp.port
                smtp_user = settings.smtp.sender_email
                smtp_password = settings.smtp.app_password
        except Exception:
            pass

    if not smtp_user or not smtp_password:
        logger.info(f"🔑 [PASSWORD RECOVERY] Generated 6-digit OTP for {to_email}: {otp_code} (SMTP not configured, logging code for preview)")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Your Password Reset Code: {otp_code} - Autonomous Job Agent"
        msg["From"] = f"Autonomous Job Agent <{smtp_user}>"
        msg["To"] = to_email

        html_content = f"""
        <html>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0f172a; padding: 30px; margin: 0;">
          <div style="max-width: 480px; margin: 0 auto; background-color: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 28px; color: #f8fafc;">
            <h2 style="margin-top: 0; color: #818cf8; font-size: 20px;">Autonomous Job Agent</h2>
            <h3 style="margin-bottom: 8px; color: #f8fafc; font-size: 17px;">Password Reset Verification</h3>
            <p style="color: #94a3b8; font-size: 14px; line-height: 1.5;">Hello <strong>{recipient_name}</strong>,</p>
            <p style="color: #94a3b8; font-size: 14px; line-height: 1.5;">You requested to reset your password. Use the single-use 6-digit verification code below to proceed:</p>
            <div style="text-align: center; margin: 24px 0;">
              <span style="font-size: 32px; font-weight: 700; letter-spacing: 8px; color: #38bdf8; background: #0f172a; padding: 12px 24px; border-radius: 8px; display: inline-block; border: 1px solid #38bdf8;">{otp_code}</span>
            </div>
            <p style="color: #64748b; font-size: 12px; line-height: 1.5;">This code is valid for 10 minutes and will expire immediately after use or if a new code is requested. If you did not request this code, no action is needed.</p>
          </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        logger.info(f"📧 [EMAIL OTP] Successfully dispatched OTP email to {to_email}")
        return True
    except Exception as e:
        logger.warning(f"📧 [EMAIL OTP] SMTP dispatch warning for {to_email}: {e}")
        return False


@router.post(
    "/forgot-password/request-otp",
    response_model=ForgotPasswordResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate and dispatch 6-digit OTP for password recovery"
)
def request_password_reset_otp(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Dispatches a cryptographically secure 6-digit OTP valid for 10 minutes.
    Automatically invalidates any previous unused OTPs for this user so only the latest code works.
    """
    clean_email = payload.email.strip().lower()

    user = db.query(User).filter(User.email == clean_email, User.is_active.is_(True)).first()
    if not user:
        logger.warning(f"Password reset rejected: No active user found with email '{clean_email}'")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No registered active account found with this email address. Please sign up."
        )

    # Invalidate all previous unused OTPs for this user (Old OTP auto-invalidation rule)
    db.query(PasswordResetOTP).filter(
        PasswordResetOTP.user_id == user.id,
        PasswordResetOTP.is_used.is_(False)
    ).update({"is_used": True})

    # Generate cryptographically secure 6-digit numeric OTP
    otp_code = generate_cryptographic_otp(6)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRE_MINUTES)

    otp_record = PasswordResetOTP(
        user_id=user.id,
        email=clean_email,
        otp_code=otp_code,
        expires_at=expires_at,
        is_used=False
    )
    db.add(otp_record)
    db.commit()

    # Dispatch via email
    dispatch_otp_email(to_email=clean_email, recipient_name=user.full_name, otp_code=otp_code)

    return ForgotPasswordResponse(
        message=f"Verification OTP has been sent to {clean_email}. It is valid for {OTP_EXPIRE_MINUTES} minutes.",
        email=clean_email,
        expires_in_minutes=OTP_EXPIRE_MINUTES
    )


@router.post(
    "/forgot-password/verify-otp",
    response_model=VerifyOTPOnlyResponse,
    status_code=status.HTTP_200_OK,
    summary="Step 2: Verify 6-digit OTP and return a reset token"
)
def verify_otp_only(
    payload: VerifyOTPOnlyRequest,
    db: Session = Depends(get_db)
):
    """
    Step 2 in real-world password recovery:
    Validates whether the entered 6-digit OTP is valid, unused, and unexpired.
    Returns a signed temporary reset token allowing the user to proceed to Step 3 (Set New Password).
    """
    clean_email = payload.email.strip().lower()
    clean_otp = payload.otp.strip()

    now = datetime.now(timezone.utc)

    # 1. Locate matching unused OTP record for this email
    otp_record = db.query(PasswordResetOTP).filter(
        PasswordResetOTP.email == clean_email,
        PasswordResetOTP.otp_code == clean_otp,
        PasswordResetOTP.is_used.is_(False)
    ).order_by(PasswordResetOTP.created_at.desc()).first()

    if not otp_record:
        logger.warning(f"OTP verification failed: Invalid or already-used OTP '{clean_otp}' for '{clean_email}'")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP code. Please enter the latest code or request a fresh one."
        )

    # 2. Check expiration
    otp_expiry = otp_record.expires_at
    if otp_expiry.tzinfo is None:
        otp_expiry = otp_expiry.replace(tzinfo=timezone.utc)

    if now > otp_expiry:
        logger.warning(f"OTP verification failed: Expired OTP '{clean_otp}' for '{clean_email}'")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This OTP verification code has expired (10-minute limit). Please request a fresh code."
        )

    # 3. Mark OTP as consumed immediately (Strict Anti-Replay Protection)
    otp_record.is_used = True
    db.commit()

    # 4. Generate short-lived reset token (valid for 15 minutes)
    reset_token = create_access_token(
        user_id=otp_record.user_id,
        email=clean_email,
        expires_delta=timedelta(minutes=15)
    )

    logger.info(f"✅ OTP verified successfully for '{clean_email}'. Proceeding to Step 3.")
    return VerifyOTPOnlyResponse(
        valid=True,
        message="OTP verified successfully. Please enter your new password.",
        reset_token=reset_token
    )


@router.post(
    "/forgot-password/set-new-password",
    response_model=ResetPasswordResponse,
    status_code=status.HTTP_200_OK,
    summary="Step 3: Set new password using verified reset token"
)
def set_new_password(
    payload: SetNewPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Step 3 in real-world password recovery:
    Validates reset token and updates the user's password with a fresh bcrypt hash.
    Invalidates any remaining unused OTPs for this user to permanently prevent replay attacks.
    """
    clean_email = payload.email.strip().lower()

    # 1. Decode and validate reset token
    token_payload = decode_access_token(payload.reset_token)
    if not token_payload or token_payload.get("email") != clean_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired password reset session. Please verify your OTP again."
        )

    user_id = int(token_payload["sub"])
    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated user account not found."
        )

    # 2. Update user's password with fresh bcrypt hash
    new_hash = hash_password(payload.new_password)
    user.password_hash = new_hash

    # 3. Mark all unused OTPs as consumed (Permanent replay prevention)
    db.query(PasswordResetOTP).filter(
        PasswordResetOTP.user_id == user.id,
        PasswordResetOTP.is_used.is_(False)
    ).update({"is_used": True})
    db.commit()

    logger.info(f"Password reset completed successfully for User #{user.id} ({user.email}).")
    return ResetPasswordResponse(
        success=True,
        message="Your password has been successfully reset. You can now sign in with your new password."
    )


@router.post(
    "/forgot-password/verify-reset",
    response_model=ResetPasswordResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify 6-digit OTP and reset password (Legacy / Backward Compatibility)"
)
def verify_otp_and_reset_password(
    payload: VerifyOTPResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Validates unexpired 6-digit OTP and updates the user's password with a fresh bcrypt hash.
    Marks OTP as consumed to prevent replay attacks.
    """
    clean_email = payload.email.strip().lower()
    clean_otp = payload.otp.strip()

    now = datetime.now(timezone.utc)

    # 1. Locate matching unused OTP record
    otp_record = db.query(PasswordResetOTP).filter(
        PasswordResetOTP.email == clean_email,
        PasswordResetOTP.otp_code == clean_otp,
        PasswordResetOTP.is_used.is_(False)
    ).order_by(PasswordResetOTP.created_at.desc()).first()

    if not otp_record:
        logger.warning(f"Password reset failed: Invalid OTP '{clean_otp}' for '{clean_email}'")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP verification code. Please check your code or request a fresh one."
        )

    # 2. Check expiration
    otp_expiry = otp_record.expires_at
    if otp_expiry.tzinfo is None:
        otp_expiry = otp_expiry.replace(tzinfo=timezone.utc)

    if now > otp_expiry:
        logger.warning(f"Password reset failed: Expired OTP '{clean_otp}' for '{clean_email}'")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This OTP verification code has expired. Please request a new code."
        )

    # 3. Lookup user
    user = db.query(User).filter(User.id == otp_record.user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated user account not found."
        )

    # 4. Hash new password and update user
    new_hash = hash_password(payload.new_password)
    user.password_hash = new_hash

    # 5. Mark OTP as consumed (Replay prevention)
    otp_record.is_used = True
    db.commit()

    logger.info(f"Password reset successful for User #{user.id} ({user.email}) via verified OTP.")

    return ResetPasswordResponse(
        success=True,
        message="Your password has been successfully reset. You can now log in with your new password."
    )
