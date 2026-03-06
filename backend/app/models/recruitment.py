"""
Recruitment Models

Data models for job descriptions, resumes, and analysis results.
These models represent structured data for the recruitment analysis workflow.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ============================================================
# JOB DESCRIPTION MODELS
# ============================================================

class EmploymentType(str, Enum):
    """Types of employment."""
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    TEMPORARY = "temporary"
    INTERNSHIP = "internship"
    FREELANCE = "freelance"


class ExperienceLevel(str, Enum):
    """Required experience levels."""
    ENTRY = "entry"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    EXECUTIVE = "executive"


class WorkLocation(str, Enum):
    """Work location types."""
    ON_SITE = "on_site"
    HYBRID = "hybrid"
    REMOTE = "remote"


class Skill(BaseModel):
    """A skill with optional proficiency level."""
    name: str
    category: Optional[str] = None  # e.g., "programming", "language", "soft_skill"
    required: bool = True
    proficiency_level: Optional[str] = None  # e.g., "beginner", "intermediate", "expert"


class JobDescription(BaseModel):
    """Structured job description data."""
    # Basic info
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    work_location: WorkLocation = WorkLocation.ON_SITE
    employment_type: EmploymentType = EmploymentType.FULL_TIME

    # Experience
    experience_level: ExperienceLevel = ExperienceLevel.MID
    years_of_experience: Optional[ tuple[int, int] ] = Field(
        default=None,
        description="Min and max years of experience required",
    )

    # Skills
    required_skills: List[Skill] = Field(default_factory=list)
    preferred_skills: List[Skill] = Field(default_factory=list)

    # Responsibilities
    responsibilities: List[str] = Field(default_factory=list)

    # Requirements
    requirements: List[str] = Field(default_factory=list)

    # Benefits
    benefits: List[str] = Field(default_factory=list)

    # Salary
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: str = "USD"

    # Metadata
    description_text: str = Field(default="", description="Full raw job description text")
    posted_date: Optional[datetime] = None
    application_deadline: Optional[datetime] = None

    # Analysis metadata
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    missing_fields: List[str] = Field(default_factory=list)


# ============================================================
# RESUME MODELS
# ============================================================

class Education(BaseModel):
    """Educational background."""
    institution: str
    degree: str
    field_of_study: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    gpa: Optional[float] = None
    honors: List[str] = Field(default_factory=list)


class WorkExperience(BaseModel):
    """Work experience entry."""
    company: str
    title: str
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    current: bool = False
    description: List[str] = Field(default_factory=list)
    skills_used: List[str] = Field(default_factory=list)


class Certification(BaseModel):
    """Professional certification."""
    name: str
    issuer: Optional[str] = None
    issue_date: Optional[str] = None
    expiration_date: Optional[str] = None
    credential_url: Optional[str] = None


class Resume(BaseModel):
    """Structured resume data."""
    # Personal info
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    links: List[str] = Field(default_factory=list)  # LinkedIn, portfolio, etc.

    # Summary
    summary: Optional[str] = None

    # Experience
    work_experience: List[WorkExperience] = Field(default_factory=list)

    # Education
    education: List[Education] = Field(default_factory=list)

    # Skills
    skills: List[Skill] = Field(default_factory=list)

    # Certifications
    certifications: List[Certification] = Field(default_factory=list)

    # Languages
    languages: List[Dict[str, str]] = Field(default_factory=list)  # [{"language": "English", "proficiency": "native"}]

    # Projects
    projects: List[Dict[str, Any]] = Field(default_factory=list)

    # Metadata
    resume_text: str = Field(default="", description="Full raw resume text")
    parsed_date: datetime = Field(default_factory=datetime.utcnow)
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    missing_fields: List[str] = Field(default_factory=list)


# ============================================================
# ANALYSIS RESULT MODELS
# ============================================================

class SkillMatch(BaseModel):
    """Analysis of a single skill match."""
    skill: str
    in_job: bool
    in_resume: bool
    match_quality: str  # "exact", "partial", "missing"


class MatchAnalysis(BaseModel):
    """Detailed match analysis between job and resume."""
    overall_score: float = Field(ge=0.0, le=100.0, description="Overall match percentage")
    skill_matches: List[SkillMatch] = Field(default_factory=list)
    skill_score: float = Field(ge=0.0, le=100.0, description="Skills match percentage")

    experience_match: bool
    experience_note: str

    education_match: bool
    education_note: str

    # Gap analysis
    missing_required_skills: List[str] = Field(default_factory=list)
    missing_preferred_skills: List[str] = Field(default_factory=list)
    additional_skills: List[str] = Field(default_factory=list)

    # Recommendations
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


class RecruitmentAnalysis(BaseModel):
    """Complete recruitment analysis result."""
    analysis_id: str
    session_id: str

    # Input data references
    job_description_id: Optional[str] = None
    resume_id: Optional[str] = None

    # Parsed data
    job_description: Optional[JobDescription] = None
    resume: Optional[Resume] = None

    # Match analysis
    match_analysis: Optional[MatchAnalysis] = None

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    llm_model: str = Field(default="analyst-agent", description="Model used for analysis")
    processing_time_seconds: float = 0.0

    # AI-generated insights
    insights: List[str] = Field(default_factory=list)
    red_flags: List[str] = Field(default_factory=list)

    model_config = {"protected_namespaces": ()}


class JDAnalysis(BaseModel):
    """Job Description analysis result."""
    analysis_id: str
    session_id: str

    # Parsed job data
    job_description: JobDescription

    # Analysis metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    llm_model: str = Field(default="analyst-agent", description="Model used for analysis")
    processing_time_seconds: float = 0.0

    # Key insights
    key_requirements: List[str] = Field(default_factory=list)
    deal_breakers: List[str] = Field(default_factory=list)
    nice_to_haves: List[str] = Field(default_factory=list)

    model_config = {"protected_namespaces": ()}


class ResumeAnalysis(BaseModel):
    """Resume analysis result."""
    analysis_id: str
    session_id: str

    # Parsed resume data
    resume: Resume

    # Analysis metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    llm_model: str = Field(default="analyst-agent", description="Model used for analysis")
    processing_time_seconds: float = 0.0

    # Key insights
    key_strengths: List[str] = Field(default_factory=list)
    areas_for_improvement: List[str] = Field(default_factory=list)
    suggested_roles: List[str] = Field(default_factory=list)
    total_years_experience: float = 0.0

    model_config = {"protected_namespaces": ()}
