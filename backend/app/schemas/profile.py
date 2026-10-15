"""
Module: profile.py
Purpose: Pydantic Schema for Candidate Master Profile.
Standards: Rule 1 (Type-Safety), Rule 2 (Input Validation), Rule 3 (Concise & Accurate).
"""
from typing import List, Optional
from pydantic import BaseModel, Field

class PersonalInfo(BaseModel):
    name: str = Field(..., description="Candidate full legal name")
    email: str = Field(..., description="Primary professional email address")
    phone: str = Field(..., description="Contact phone number with country code")
    location: str = Field(..., description="Current city/state/country")
    linkedin_url: Optional[str] = Field(default="", description="Public LinkedIn profile URL")
    github_url: Optional[str] = Field(default="", description="Public GitHub profile URL")
    portfolio_url: Optional[str] = Field(default="", description="Personal website or portfolio URL")

class Preferences(BaseModel):
    target_roles: List[str] = Field(default_factory=list, description="Target job titles (e.g. Junior AI Engineer)")
    preferred_locations: List[str] = Field(default_factory=list, description="Cities or Remote preferences")
    work_modes: List[str] = Field(default_factory=lambda: ["Remote", "Hybrid"], description="Work styles")
    min_expected_salary: Optional[str] = Field(default="", description="Expected CTC / salary range")
    notice_period_days: int = Field(default=0, description="Notice period in days (0 = Immediate joiner)")

class TechnicalSkills(BaseModel):
    programming_languages: List[str] = Field(default_factory=list)
    frameworks_and_libraries: List[str] = Field(default_factory=list)
    ai_and_ml: List[str] = Field(default_factory=list)
    databases: List[str] = Field(default_factory=list)
    tools_and_platforms: List[str] = Field(default_factory=list)

class WorkExperience(BaseModel):
    role: str
    company: str
    location: str
    start_date: str
    end_date: str
    is_current: bool = False
    highlights: List[str] = Field(default_factory=list, description="Bullet points detailing impact and technologies")

class Project(BaseModel):
    title: str
    tech_stack: List[str] = Field(default_factory=list)
    description: str
    key_achievements: List[str] = Field(default_factory=list)
    live_url: Optional[str] = ""
    github_url: Optional[str] = ""

class Education(BaseModel):
    degree: str
    field_of_study: str
    institution: str
    graduation_year: int

class ApplicationAnswers(BaseModel):
    immediate_joiner: bool = True
    willing_to_relocate: bool = True
    years_of_experience: float = Field(default=0.8, description="Total professional experience in years")
    work_authorization: str = Field(default="Authorized to work in India", description="Visa or work status")
    custom_qa: dict = Field(default_factory=dict, description="Custom screening question responses")

class CandidateProfile(BaseModel):
    """The master root schema representing the full candidate profile."""
    personal_info: PersonalInfo
    preferences: Preferences
    technical_skills: TechnicalSkills
    experience: List[WorkExperience] = Field(default_factory=list)
    projects: List[Project] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    application_answers: ApplicationAnswers = Field(default_factory=ApplicationAnswers)
