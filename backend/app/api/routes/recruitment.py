"""
Recruitment Analysis API Routes

FastAPI endpoints for the JobAnalystAgent.
Provides job description parsing, resume parsing, and match analysis.
"""

import base64
import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Depends, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.agents.job_analyst import JobAnalystAgent, create_job_analyst_agent
from app.agents.base_agent import AgentContext
from app.models.recruitment import (
    JDAnalysis,
    ResumeAnalysis,
    RecruitmentAnalysis,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/recruitment",
    tags=["Recruitment Analysis"],
    responses={404: {"description": "Not found"}},
)


# ============================================================
# REQUEST/RESPONSE MODELS
# ============================================================

class ParseJDRequest(BaseModel):
    """Request to parse a job description."""
    job_description_text: str = Field(
        ...,
        description="Raw job description text",
    )
    session_id: Optional[str] = Field(
        None,
        description="Session ID for context persistence",
    )


class ParseResumeRequest(BaseModel):
    """Request to parse a resume."""
    resume_text: str = Field(
        ...,
        description="Raw resume text",
    )
    session_id: Optional[str] = Field(
        None,
        description="Session ID for context persistence",
    )


class MatchAnalysisRequest(BaseModel):
    """Request to analyze job-resume match."""
    job_description_id: Optional[str] = Field(
        None,
        description="Job description analysis ID (from previous parse_jd)",
    )
    resume_id: Optional[str] = Field(
        None,
        description="Resume analysis ID (from previous parse_resume)",
    )
    job_description: Optional[Dict[str, Any]] = Field(
        None,
        description="Structured job description (if not using ID)",
    )
    resume: Optional[Dict[str, Any]] = Field(
        None,
        description="Structured resume (if not using ID)",
    )
    session_id: Optional[str] = Field(
        None,
        description="Session ID for context persistence",
    )


class StandardResponse(BaseModel):
    """Standard API response wrapper."""
    success: bool
    message: Optional[str] = None
    data: Optional[Any] = None
    errors: Optional[List[str]] = None


# ============================================================
# DEPENDENCIES
# ============================================================

# Singleton agent instance
_agent_instance: Optional[JobAnalystAgent] = None


def get_job_analyst_agent() -> JobAnalystAgent:
    """
    Get or create the JobAnalystAgent singleton.

    Returns:
        JobAnalystAgent instance
    """
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = create_job_analyst_agent()
    return _agent_instance


# ============================================================
# ENDPOINTS
# ============================================================

@router.post("/parse-jd", response_model=Dict[str, Any])
async def parse_job_description(
    request: ParseJDRequest,
    agent: JobAnalystAgent = Depends(get_job_analyst_agent),
) -> Dict[str, Any]:
    """
    Parse a job description into structured data.

    Extracts:
    - Job title, company, location
    - Employment type, work location type
    - Required and preferred skills
    - Responsibilities and requirements
    - Salary information
    - Benefits

    The result is stored in session-scoped memory for subsequent analyses.
    """
    try:
        # Create context
        session_id = request.session_id or str(uuid.uuid4())
        context = AgentContext(session_id=session_id)

        # Parse job description
        result = await agent.parse_job_description(
            context=context,
            job_description_text=request.job_description_text,
        )

        return {
            "success": True,
            "message": "Job description parsed successfully",
            "data": {
                "analysis_id": result.analysis_id,
                "session_id": result.session_id,
                "job_description": result.job_description.model_dump(),
                "key_requirements": result.key_requirements,
                "deal_breakers": result.deal_breakers,
                "nice_to_haves": result.nice_to_haves,
                "llm_model": result.llm_model,
                "processing_time_seconds": result.processing_time_seconds,
            },
        }

    except Exception as e:
        logger.error(f"Error parsing job description: {e}", exc_info=True)
        return {
            "success": False,
            "message": "Failed to parse job description",
            "errors": [str(e)],
        }


@router.post("/parse-jd/file", response_model=Dict[str, Any])
async def parse_job_description_from_file(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    agent: JobAnalystAgent = Depends(get_job_analyst_agent),
) -> Dict[str, Any]:
    """
    Parse a job description from an uploaded file.

    Supported formats: PDF, DOCX, TXT, JSON, MD
    """
    try:
        # Read file content
        content = await file.read()
        file_content_base64 = base64.b64encode(content).decode("utf-8")

        # Create context
        context = AgentContext(session_id=session_id or str(uuid.uuid4()))

        # Parse job description
        result = await agent.parse_job_description(
            context=context,
            file_content=file_content_base64,
        )

        return {
            "success": True,
            "message": f"Job description parsed from {file.filename}",
            "data": {
                "analysis_id": result.analysis_id,
                "session_id": result.session_id,
                "job_description": result.job_description.model_dump(),
                "key_requirements": result.key_requirements,
                "deal_breakers": result.deal_breakers,
                "nice_to_haves": result.nice_to_haves,
                "llm_model": result.llm_model,
                "processing_time_seconds": result.processing_time_seconds,
            },
        }

    except Exception as e:
        logger.error(f"Error parsing job description from file: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Failed to parse job description from {file.filename}",
            "errors": [str(e)],
        }


@router.post("/parse-resume", response_model=Dict[str, Any])
async def parse_resume(
    request: ParseResumeRequest,
    agent: JobAnalystAgent = Depends(get_job_analyst_agent),
) -> Dict[str, Any]:
    """
    Parse a resume into structured data.

    Extracts:
    - Personal information (name, email, phone, location)
    - Work experience with dates and descriptions
    - Education history
    - Skills (categorized)
    - Certifications
    - Languages
    - Projects

    The result is stored in session-scoped memory for subsequent analyses.
    """
    try:
        # Create context
        session_id = request.session_id or str(uuid.uuid4())
        context = AgentContext(session_id=session_id)

        # Parse resume
        result = await agent.parse_resume(
            context=context,
            resume_text=request.resume_text,
        )

        return {
            "success": True,
            "message": "Resume parsed successfully",
            "data": {
                "analysis_id": result.analysis_id,
                "session_id": result.session_id,
                "resume": result.resume.model_dump(),
                "key_strengths": result.key_strengths,
                "areas_for_improvement": result.areas_for_improvement,
                "suggested_roles": result.suggested_roles,
                "total_years_experience": result.total_years_experience,
                "llm_model": result.llm_model,
                "processing_time_seconds": result.processing_time_seconds,
            },
        }

    except Exception as e:
        logger.error(f"Error parsing resume: {e}", exc_info=True)
        return {
            "success": False,
            "message": "Failed to parse resume",
            "errors": [str(e)],
        }


@router.post("/parse-resume/file", response_model=Dict[str, Any])
async def parse_resume_from_file(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    agent: JobAnalystAgent = Depends(get_job_analyst_agent),
) -> Dict[str, Any]:
    """
    Parse a resume from an uploaded file.

    Supported formats: PDF, DOCX, TXT, JSON, MD
    """
    try:
        # Read file content
        content = await file.read()
        file_content_base64 = base64.b64encode(content).decode("utf-8")

        # Create context
        context = AgentContext(session_id=session_id or str(uuid.uuid4()))

        # Parse resume
        result = await agent.parse_resume(
            context=context,
            file_content=file_content_base64,
        )

        return {
            "success": True,
            "message": f"Resume parsed from {file.filename}",
            "data": {
                "analysis_id": result.analysis_id,
                "session_id": result.session_id,
                "resume": result.resume.model_dump(),
                "key_strengths": result.key_strengths,
                "areas_for_improvement": result.areas_for_improvement,
                "suggested_roles": result.suggested_roles,
                "total_years_experience": result.total_years_experience,
                "llm_model": result.llm_model,
                "processing_time_seconds": result.processing_time_seconds,
            },
        }

    except Exception as e:
        logger.error(f"Error parsing resume from file: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Failed to parse resume from {file.filename}",
            "errors": [str(e)],
        }


@router.post("/match-analysis", response_model=Dict[str, Any])
async def analyze_match(
    request: MatchAnalysisRequest,
    agent: JobAnalystAgent = Depends(get_job_analyst_agent),
) -> Dict[str, Any]:
    """
    Analyze the match between a job description and a resume.

    This endpoint performs a detailed comparison including:
    - Overall match score (0-100)
    - Skill-by-skill analysis
    - Experience fit evaluation
    - Education requirements check
    - Missing and additional skills
    - Strengths, weaknesses, and recommendations

    Uses data from previous parse_jd and parse_resume calls if IDs are provided.
    Can also accept structured job/resume data directly.
    """
    try:
        # Create context
        session_id = request.session_id or str(uuid.uuid4())
        context = AgentContext(session_id=session_id)

        # Perform match analysis
        result = await agent.analyze_match(
            context=context,
            job_description=request.job_description,
            resume=request.resume,
        )

        return {
            "success": True,
            "message": "Match analysis completed",
            "data": {
                "analysis_id": result.analysis_id,
                "session_id": result.session_id,
                "overall_score": result.match_analysis.overall_score,
                "skill_score": result.match_analysis.skill_score,
                "experience_match": result.match_analysis.experience_match,
                "education_match": result.match_analysis.education_match,
                "skill_matches": result.match_analysis.skill_matches,
                "missing_required_skills": result.match_analysis.missing_required_skills,
                "missing_preferred_skills": result.match_analysis.missing_preferred_skills,
                "additional_skills": result.match_analysis.additional_skills,
                "strengths": result.match_analysis.strengths,
                "weaknesses": result.match_analysis.weaknesses,
                "recommendations": result.match_analysis.recommendations,
                "insights": result.insights,
                "red_flags": result.red_flags,
                "llm_model": result.llm_model,
                "processing_time_seconds": result.processing_time_seconds,
            },
        }

    except Exception as e:
        logger.error(f"Error analyzing match: {e}", exc_info=True)
        return {
            "success": False,
            "message": "Failed to analyze match",
            "errors": [str(e)],
        }


@router.get("/health", response_model=Dict[str, Any])
async def health_check(
    agent: JobAnalystAgent = Depends(get_job_analyst_agent),
) -> Dict[str, Any]:
    """
    Health check endpoint for the JobAnalystAgent.

    Returns agent status and configuration.
    """
    return {
        "success": True,
        "data": {
            "agent": agent.config.name,
            "role": agent.config.role.value,
            "model": agent.config.model_alias,
            "state": agent.state.value,
            "memory_enabled": agent.config.enable_long_term_memory,
            "memory_collection": agent.config.memory_collection,
        },
    }


@router.post("/a2a", response_model=Dict[str, Any])
async def a2a_endpoint(
    request: Dict[str, Any],
    agent: JobAnalystAgent = Depends(get_job_analyst_agent),
) -> Dict[str, Any]:
    """
    A2A Protocol endpoint for inter-agent communication.

    Accepts A2A protocol messages and routes them to appropriate handlers.
    Supported task types:
    - parse_jd: Parse job description
    - parse_resume: Parse resume
    - match_analysis: Analyze job-resume match
    - health_check: Agent health status
    """
    try:
        from app.agents.a2a import A2AMessage

        # Parse A2A message
        message = A2AMessage(**request)

        # Handle request
        response = await agent.handle_a2a_request(message)

        return {
            "success": response.status.code.value == "ok",
            "data": response.dict(),
        }

    except Exception as e:
        logger.error(f"Error handling A2A request: {e}", exc_info=True)
        return {
            "success": False,
            "message": "A2A request failed",
            "errors": [str(e)],
        }


@router.get("/session/{session_id}", response_model=Dict[str, Any])
async def get_session_data(
    session_id: str,
    agent: JobAnalystAgent = Depends(get_job_analyst_agent),
) -> Dict[str, Any]:
    """
    Retrieve all analysis data for a session.

    Returns job description, resume, and match analysis if available.
    """
    try:
        context = AgentContext(session_id=session_id)

        # Load all data from memory
        jd_data = await agent.load_from_memory("last_jd_analysis", context)
        resume_data = await agent.load_from_memory("last_resume_analysis", context)
        match_data = await agent.load_from_memory("last_match_analysis", context)

        return {
            "success": True,
            "data": {
                "session_id": session_id,
                "job_description": jd_data,
                "resume": resume_data,
                "match_analysis": match_data,
            },
        }

    except Exception as e:
        logger.error(f"Error retrieving session data: {e}", exc_info=True)
        return {
            "success": False,
            "message": "Failed to retrieve session data",
            "errors": [str(e)],
        }
