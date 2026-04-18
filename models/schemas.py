"""Pydantic contracts — profile uses free-text lists + structured work history."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Opportunity(BaseModel):
    model_config = ConfigDict(extra="ignore")

    is_genuine: bool = True
    title: str
    type: str = "Unknown"
    deadline: str = "TBD"
    required_skills: List[str] = Field(default_factory=list)
    opportunity_interests: List[str] = Field(default_factory=list)
    why_it_matters: str = ""

    eligibility_conditions: List[str] = Field(default_factory=list)
    required_documents: List[str] = Field(default_factory=list)
    application_links: List[str] = Field(default_factory=list)
    contacts: List[str] = Field(default_factory=list)
    next_steps: List[str] = Field(default_factory=list)
    evidence_quotes: List[str] = Field(default_factory=list)
    min_cgpa: Optional[float] = None


class WorkExperienceEntry(BaseModel):
    """LinkedIn-style role (one row per job / internship)."""

    model_config = ConfigDict(extra="ignore")

    job_title: str = Field(default="", max_length=200)
    company: str = Field(default="", max_length=200)
    date_started: str = Field(default="", max_length=80)
    date_ended: str = Field(default="", max_length=80)
    currently_working: bool = False

    @field_validator("job_title", "company", mode="before")
    @classmethod
    def _strip_title_company(cls, v: object) -> str:
        if v is None:
            return ""
        return str(v).strip()[:200]

    @field_validator("date_started", "date_ended", mode="before")
    @classmethod
    def _strip_dates(cls, v: object) -> str:
        if v is None:
            return ""
        return str(v).strip()[:80]


DegreeProgram = Literal[
    "BS Computer Science",
    "BS Software Engineering",
    "BS Electrical Engineering",
    "BS Data Science",
    "BBA",
    "MS Computer Science",
    "Other / Undeclared",
]

SemesterTerm = Literal[
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "Graduated",
]

LocationPreference = Literal[
    "Any",
    "Remote only",
    "Lahore",
    "Islamabad",
    "Karachi",
    "On-site (any major city)",
]


class StudentProfile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(default="", max_length=120)
    degree_program: DegreeProgram = "Other / Undeclared"
    semester: SemesterTerm = "1"
    cgpa: Optional[float] = None
    skills: List[str] = Field(default_factory=list)
    interests: List[str] = Field(default_factory=list)
    preferred_opportunity_types: List[str] = Field(default_factory=list)
    financial_need: Literal["none", "low", "medium", "high"] = "none"
    location_preference: LocationPreference = "Any"
    work_experience: List[WorkExperienceEntry] = Field(default_factory=list)

    graduation_year: Optional[int] = None

    @field_validator("name", mode="before")
    @classmethod
    def _strip_name(cls, v: object) -> str:
        if v is None:
            return ""
        s = str(v).strip()
        return s[:120]


SAMPLE_PROFILE = StudentProfile(
    name="Alex Chen",
    degree_program="BS Computer Science",
    semester="6",
    cgpa=3.45,
    skills=["Python", "Machine Learning", "SQL", "Communication"],
    interests=["Artificial Intelligence", "Quantum computing"],
    preferred_opportunity_types=["Internship"],
    financial_need="medium",
    location_preference="Any",
    work_experience=[
        WorkExperienceEntry(
            job_title="Teaching Assistant",
            company="FAST-NU",
            date_started="Aug 2024",
            date_ended="",
            currently_working=True,
        ),
        WorkExperienceEntry(
            job_title="Summer Intern",
            company="Tech Corp",
            date_started="Jun 2024",
            date_ended="Aug 2024",
            currently_working=False,
        ),
    ],
    graduation_year=2026,
)

PREFERRED_OPPORTUNITY_TYPE_OPTIONS: List[str] = [
    "Scholarship",
    "Internship",
    "Fellowship",
    "Competition",
    "Admission",
    "Research",
    "Other",
]

# Optional hints for LLM prompts (not enforced in UI).
SKILL_SUGGESTIONS: List[str] = [
    "Python",
    "Java",
    "Machine Learning",
    "SQL",
    "Communication",
]

INTEREST_SUGGESTIONS: List[str] = [
    "Artificial Intelligence",
    "Cybersecurity",
    "Web / cloud",
]

DEGREE_PROGRAM_OPTIONS: List[str] = [
    "BS Computer Science",
    "BS Software Engineering",
    "BS Electrical Engineering",
    "BS Data Science",
    "BBA",
    "MS Computer Science",
    "Other / Undeclared",
]

SEMESTER_OPTIONS: List[str] = [
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "Graduated",
]

LOCATION_OPTIONS: List[str] = [
    "Any",
    "Remote only",
    "Lahore",
    "Islamabad",
    "Karachi",
    "On-site (any major city)",
]
