"""
Module: security.py
Purpose: Enterprise-Grade Cryptographic Security & JWT Authentication Engine.
Standards: Rule 1 (Zero Vulnerability - Bcrypt salt, timing-safe compare, PyJWT signature verification),
           Rule 2 (Strict Type Hints & Pydantic), Rule 5 (ACID & Production Standard).
"""
import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status, Request, Query
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import (
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    OTP_EXPIRE_MINUTES,
)
from app.db.session import get_db
from app.db.models import User

logger = logging.getLogger("core.security")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def hash_password(plain_password: str) -> str:
    """
    Hashes a plaintext password using direct bcrypt with a random salt (cost factor: 12).
    Never stores plain passwords in memory longer than necessary.
    """
    if not plain_password:
        raise ValueError("Password cannot be empty.")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plaintext password against a bcrypt hash in constant time,
    preventing side-channel timing attacks.
    """
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception as e:
        logger.warning(f"Bcrypt verification error: {e}")
        return False


def create_access_token(
    user_id: int,
    email: str,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Generates a cryptographically signed JWT access token.
    Default validity: 7 days (ACCESS_TOKEN_EXPIRE_MINUTES).
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload: Dict[str, Any] = {
        "sub": str(user_id),
        "email": email.strip().lower(),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    encoded_jwt = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decodes and validates JWT token integrity and signature.
    Returns payload dict if valid, None if expired or tampered with.
    """
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.debug("JWT Access Token has expired.")
        return None
    except jwt.PyJWTError as e:
        logger.warning(f"Invalid JWT Token signature: {e}")
        return None


def generate_cryptographic_otp(length: int = 6) -> str:
    """
    Generates a cryptographically secure numeric OTP using OS CSPRNG (secrets module).
    Avoids pseudo-random PRNG predictability.
    """
    # 6-digit random number between 100000 and 999999
    return "".join(secrets.choice("0123456789") for _ in range(length))


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    FastAPI dependency: Resolves the authenticated User from the Bearer JWT token.
    Raises HTTP 401 Unauthorized if token is missing, expired, or invalid.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials or token expired. Please log in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception

    payload = decode_access_token(token)
    if not payload:
        raise credentials_exception

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise credentials_exception

    try:
        user_id = int(user_id_str)
    except ValueError:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or has been deactivated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def get_optional_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Resolves authenticated user from Bearer JWT token.
    If a Bearer token is provided, strictly validates it and resolves the user (or raises 401).
    If NO token is provided (e.g. legacy scripts / headless CLI tests), gracefully falls back to User #1.
    """
    if token:
        payload = decode_access_token(token)
        if not payload or not payload.get("sub"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired or invalid token. Please sign in again.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            user_id = int(payload["sub"])
            user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User account not found or has been deactivated.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return user
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # If no token is provided, return None (Zero silent fallback to User #1)
    return None


def get_current_user_from_token_or_header(
    request: Request,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db)
) -> User:
    """
    Resolves the authenticated User from either:
    1. Authorization: Bearer <jwt> header
    2. ?token=<jwt> query parameter (for direct browser file downloads <a href>, <iframe>)
    Raises HTTP 401 Unauthorized if token is missing, invalid, or expired.
    """
    jwt_str = token if isinstance(token, str) and token.strip() else None
    if not jwt_str and request:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            jwt_str = auth_header.split(" ", 1)[1].strip()

    if not jwt_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required. Provide Authorization header or ?token= query parameter.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(jwt_str)
    if not payload or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials or token expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = int(payload["sub"])
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or has been deactivated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user

