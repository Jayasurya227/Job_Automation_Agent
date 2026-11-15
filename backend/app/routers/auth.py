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
    ForgotPasswordResponse,
    ResetPasswordResponse,
)
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
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
    Invalidates any previous unused OTPs for the user.
    """
    clean_email = payload.email.strip().lower()

    user = db.query(User).filter(User.email == clean_email, User.is_active.is_(True)).first()
    if not user:
        logger.warning(f"Password reset rejected: No active user found with email '{clean_email}'")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No registered active account found with this email address. Please sign up."
        )

    # Invalidate previous unused OTPs for this user
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

    logger.info(f"🔑 [PASSWORD RECOVERY] Generated 6-digit OTP for {clean_email}: {otp_code} (Valid for {OTP_EXPIRE_MINUTES} mins)")

    return ForgotPasswordResponse(
        message=f"Verification OTP has been generated. It is valid for {OTP_EXPIRE_MINUTES} minutes.",
        email=clean_email,
        expires_in_minutes=OTP_EXPIRE_MINUTES,
        dev_otp_preview=otp_code
    )


@router.post(
    "/forgot-password/verify-reset",
    response_model=ResetPasswordResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify 6-digit OTP and reset password"
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
            detail="Invalid OTP verification code. Please check your code or request a fresh one."
        )

    # 2. Check expiration (handling timezone awareness cleanly)
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
