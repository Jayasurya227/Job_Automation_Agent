"""
Module: auth.py
Purpose: Pydantic schemas for multi-tenant user authentication, registration, and tokens.
Standards: Rule 1 (Zero Hallucination), Rule 2 (Strict Type & Schema Enforcement), Rule 5 (Production Standard).
"""
import re
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


class UserRegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100, description="User full legal name")
    email: str = Field(..., min_length=5, max_length=255, description="Unique email address for login")
    password: str = Field(..., min_length=6, max_length=128, description="Security password")

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        clean = v.strip().lower()
        if not EMAIL_REGEX.match(clean):
            raise ValueError("Invalid email address format.")
        return clean


class UserLoginRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255, description="Registered email address")
    password: str = Field(..., min_length=1, description="Account password")

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        clean = v.strip().lower()
        if not EMAIL_REGEX.match(clean):
            raise ValueError("Invalid email address format.")
        return clean


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255, description="Registered account email")

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        clean = v.strip().lower()
        if not EMAIL_REGEX.match(clean):
            raise ValueError("Invalid email address format.")
        return clean


class VerifyOTPResetPasswordRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255, description="Registered account email")
    otp: str = Field(..., min_length=6, max_length=6, description="6-digit verification OTP code")
    new_password: str = Field(..., min_length=6, max_length=128, description="New security password")

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        clean = v.strip().lower()
        if not EMAIL_REGEX.match(clean):
            raise ValueError("Invalid email address format.")
        return clean

    @field_validator("otp")
    @classmethod
    def validate_otp_format(cls, v: str) -> str:
        clean = v.strip()
        if not (len(clean) == 6 and clean.isdigit()):
            raise ValueError("OTP must be exactly 6 digits.")
        return clean


class ForgotPasswordResponse(BaseModel):
    message: str
    email: str
    expires_in_minutes: int


class ResetPasswordResponse(BaseModel):
    success: bool
    message: str
