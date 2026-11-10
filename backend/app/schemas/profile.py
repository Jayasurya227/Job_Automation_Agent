"""
Module: profile.py
Purpose: Pydantic Schema for Candidate Master Profile.
Standards: Rule 1 (Type-Safety), Rule 2 (Input Validation), Rule 3 (Concise & Accurate).
"""
from typing import List, Optional, Union
from pydantic import BaseModel, Field, field_validator
import re

class PersonalInfo(BaseModel):
    name: str = Field(default="Candidate", description="Candidate full legal name")
    email: str = Field(default="", description="Primary professional email address")
    phone: str = Field(default="", description="Contact phone number with country code")
    location: str = Field(default="", description="Current city/state/country")
    linkedin_url: Optional[str] = Field(default="", description="Public LinkedIn profile URL")
    github_url: Optional[str] = Field(default="", description="Public GitHub profile URL")
    portfolio_url: Optional[str] = Field(default="", description="Personal website or portfolio URL")

class Preferences(BaseModel):
    target_roles: List[str] = Field(default_factory=list, description="Target job titles (e.g. Junior AI Engineer)")
    preferred_locations: List[str] = Field(default_factory=list, description="Cities or Remote preferences")
    work_modes: List[str] = Field(default_factory=lambda: ["Remote", "Hybrid"], description="Work styles")
    min_expected_salary: Optional[str] = Field(default="", description="Expected CTC / salary range")
    notice_period_days: int = Field(default=0, description="Notice period in days (0 = Immediate joiner)")
    freshness_days: int = Field(default=1, ge=0, le=30, description="Default freshness filter in days (1 = last 24h, 3 = 3 days, 7 = 7 days, 0 = any)")
    experience_level: str = Field(default="0-1", description="Target experience filter: '0-1' (Fresher), '1-2' (Early Career), '2-4' (Junior/Associate), 'all' (Any)")
    autopilot_enabled: bool = Field(default=False, description="Enable automated daytime office hours runs (9:00 AM – 9:00 PM)")
    autopilot_auto_apply_score: int = Field(default=75, ge=50, le=100, description="Minimum score to auto-apply")
    autopilot_max_daily_apps: int = Field(default=7, ge=1, description="Max applications per day")
    autopilot_run_hour: int = Field(default=11, ge=0, le=23, description="Hour of day to run during office hours (e.g. 11 = 11:00 AM)")
    autopilot_run_minute: int = Field(default=0, ge=0, le=59, description="Minute of hour to run (e.g. 0)")

class TechnicalSkills(BaseModel):
    programming_languages: List[str] = Field(default_factory=list)
    frameworks_and_libraries: List[str] = Field(default_factory=list)
    ai_and_ml: List[str] = Field(default_factory=list)
    databases: List[str] = Field(default_factory=list)
    tools_and_platforms: List[str] = Field(default_factory=list)
    soft_skills: List[str] = Field(default_factory=list, description="Universal soft skills, language fluency, and core competencies")

class WorkExperience(BaseModel):
    role: str = Field(default="")
    company: str = Field(default="")
    location: str = Field(default="")
    start_date: str = Field(default="")
    end_date: str = Field(default="")
    is_current: bool = False
    highlights: List[str] = Field(default_factory=list, description="Bullet points detailing impact and technologies")

class Project(BaseModel):
    title: str = Field(default="Project")
    tech_stack: List[str] = Field(default_factory=list)
    description: str = Field(default="")
    key_achievements: List[str] = Field(default_factory=list)
    live_url: Optional[str] = ""
    github_url: Optional[str] = ""

class Education(BaseModel):
    degree: str = Field(default="")
    field_of_study: str = Field(default="")
    institution: str = Field(default="")
    graduation_year: Union[int, str] = Field(default=2025)

    @field_validator("graduation_year", mode="before")
    @classmethod
    def parse_grad_year(cls, v):
        if v is None:
            return 2025
        if isinstance(v, (int, float)):
            return int(v)
        if isinstance(v, str):
            # Extract 4-digit year like 2024 from "2020-2024" or "Expected 2026"
            matches = re.findall(r"\b(19\d\d|20\d\d)\b", v)
            if matches:
                return int(matches[-1]) # Use latest year
            v_clean = v.strip()
            if v_clean.isdigit():
                return int(v_clean)
            return v_clean
        return 2025

class ApplicationAnswers(BaseModel):
    immediate_joiner: bool = True
    willing_to_relocate: bool = True
    years_of_experience: float = Field(default=0.8, description="Total professional experience in years")
    work_authorization: str = Field(default="Authorized to work in India", description="Visa or work status")
    custom_qa: dict = Field(default_factory=dict, description="Custom screening question responses")

class CandidateProfile(BaseModel):
    """The master root schema representing the full candidate profile."""
    personal_info: PersonalInfo = Field(default_factory=PersonalInfo)
    preferences: Preferences = Field(default_factory=Preferences)
    technical_skills: TechnicalSkills = Field(default_factory=TechnicalSkills)
    experience: List[WorkExperience] = Field(default_factory=list)
    projects: List[Project] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    application_answers: ApplicationAnswers = Field(default_factory=ApplicationAnswers)
