"""
Job Analyst Agent

Specialized agent for parsing job descriptions and resumes, and performing
structured analysis. Integrates with LiteLLM for model calls, implements
memory scope, and follows A2A Protocol for inter-agent communication.

This agent is designed for recruitment workflows:
- Parse job descriptions from various formats (PDF, DOCX, TXT, JSON)
- Parse resumes from various formats
- Extract structured data from unstructured text
- Perform matching analysis between jobs and resumes
- Generate insights and recommendations
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..models.recruitment import (
    EmploymentType,
    ExperienceLevel,
    JDAnalysis,
    JobDescription,
    MatchAnalysis,
    RecruitmentAnalysis,
    Resume,
    ResumeAnalysis,
    Skill,
    WorkLocation,
    WorkExperience,
    Education,
    Certification,
)
from .base_agent import (
    AgentConfig,
    AgentContext,
    AgentResponse,
    AgentRole,
    AgentState,
    BaseAgent,
)
from .a2a import (
    A2AConfig,
    A2AProtocolAdapter,
    A2ATaskInput,
    A2ATaskOutput,
    A2AMessage,
)

logger = logging.getLogger(__name__)


class JobAnalystAgent(BaseAgent):
    """
    Job Analyst Agent - Parses job descriptions and resumes.

    This agent specializes in recruitment document analysis:
    - Job Description parsing and structuring
    - Resume parsing and structuring
    - Skills extraction and classification
    - Experience analysis
    - Job-Resume matching

    Responsibilities:
    - Parse uploaded documents (JD, resume in PDF/DOCX/TXT/JSON formats)
    - Extract key information using LLM analysis
    - Structure data according to recruitment models
    - Store results in SQLite-backed memory
    - Provide A2A Protocol-compliant communication

    Integration:
    - Uses LiteLLM with model alias "analyst-agent"
    - Stores analysis in session-scoped memory
    - Communicates via A2A Protocol with other agents
    """

    # System prompts for different analysis types
    JD_PROMPT = """You are an expert at parsing and analyzing job descriptions.

Your task is to extract structured information from a job description text.

Extract the following fields:
- title: The job title
- company: The hiring company name
- location: Geographic location
- work_location: One of: on_site, hybrid, remote
- employment_type: One of: full_time, part_time, contract, temporary, internship, freelance
- experience_level: One of: entry, mid, senior, lead, executive
- years_of_experience: Min and max years as [min, max] if specified
- required_skills: List of required skills with category
- preferred_skills: List of preferred/bonus skills
- responsibilities: List of key responsibilities
- requirements: List of requirements
- benefits: List of benefits/perks
- salary_min: Minimum salary if specified
- salary_max: Maximum salary if specified

Respond ONLY with valid JSON. Use null for missing fields."""

    RESUME_PROMPT = """You are an expert at parsing and analyzing resumes/CVs.

Your task is to extract structured information from a resume text.

Extract the following fields:
- name: Candidate's full name
- email: Email address
- phone: Phone number
- location: Geographic location
- links: URLs (LinkedIn, portfolio, GitHub, etc.)
- summary: Professional summary/objective
- work_experience: List of jobs with company, title, dates, description bullets
- education: List with institution, degree, field, dates
- skills: List of skills with category (programming, language, soft_skill, etc.)
- certifications: List with name, issuer, date
- languages: List of {language, proficiency}
- projects: List of projects with name, description, technologies

For dates, use ISO format (YYYY-MM-DD) when possible, or text like "2020" or "May 2020".

Respond ONLY with valid JSON. Use null for missing fields."""

    MATCHING_PROMPT = """You are an expert at analyzing the fit between a job description and a resume.

Compare the structured job description and resume data provided.

Provide:
1. overall_score: 0-100 match percentage
2. skill_matches: List of skills with match status (exact/partial/missing)
3. skill_score: Skills match percentage
4. experience_match: boolean if experience level matches
5. experience_note: Explanation of experience fit
6. education_match: boolean if education requirements met
7. education_note: Explanation of education fit
8. missing_required_skills: Skills required but not found
9. missing_preferred_skills: Preferred skills not found
10. additional_skills: Skills candidate has that aren't required
11. strengths: What makes this candidate a good fit
12. weaknesses: Gaps or concerns
13. recommendations: Suggestions for candidate or hiring team

Respond ONLY with valid JSON."""

    def __init__(self, config: Optional[AgentConfig] = None):
        """
        Initialize the Job Analyst Agent.

        Args:
            config: Optional agent configuration. Uses defaults if not provided.
        """
        if config is None:
            config = AgentConfig(
                name="job_analyst",
                role=AgentRole.ANALYST,
                model_alias="analyst-agent",
                temperature=0.2,  # Lower temperature for consistent parsing
                max_tokens=8192,  # Allow for detailed responses
                enable_long_term_memory=True,
                memory_collection="job_analyst_memories",
            )
        super().__init__(config)

        # Initialize A2A protocol adapter for inter-agent communication
        self._a2a = A2AProtocolAdapter(
            config=A2AConfig(
                agent_name="job_analyst",
                agent_role="analyst",
                agent_version="1.0.0",
            ),
        )

        # Register A2A message handlers
        self._register_a2a_handlers()

        logger.info("JobAnalystAgent initialized with A2A protocol support")

    def _register_a2a_handlers(self) -> None:
        """Register A2A protocol message handlers."""
        # Handlers are registered dynamically when messages are received
        # This allows the agent to respond to various task types
        self._a2a_handlers = {
            "parse_jd": self._handle_parse_jd,
            "parse_resume": self._handle_parse_resume,
            "match_analysis": self._handle_match_analysis,
            "health_check": self._handle_health_check,
        }

    async def process(
        self,
        context: AgentContext,
        input_data: Dict[str, Any],
    ) -> AgentResponse:
        """
        Process the agent's main task.

        This is the primary entry point for agent execution.
        Routes to appropriate handler based on input data.

        Args:
            context: Agent context with session ID, shared data, conversation history
            input_data: Structured input data containing task type and parameters

        Returns:
            Agent response with structured results
        """
        start_time = datetime.utcnow()
        task_type = input_data.get("task_type", "unknown")

        try:
            # Route to appropriate handler
            if task_type == "parse_jd":
                result = await self.parse_job_description(
                    context=context,
                    job_description_text=input_data.get("job_description_text", ""),
                    file_path=input_data.get("file_path"),
                    file_content=input_data.get("file_content"),
                )
                response_content = json.dumps(result.dict(), indent=2, default=str)

            elif task_type == "parse_resume":
                result = await self.parse_resume(
                    context=context,
                    resume_text=input_data.get("resume_text", ""),
                    file_path=input_data.get("file_path"),
                    file_content=input_data.get("file_content"),
                )
                response_content = json.dumps(result.dict(), indent=2, default=str)

            elif task_type == "match_analysis":
                # Get JD and Resume from memory or input
                jd_data = input_data.get("job_description")
                resume_data = input_data.get("resume")

                result = await self.analyze_match(
                    context=context,
                    job_description=jd_data,
                    resume=resume_data,
                )
                response_content = json.dumps(result.dict(), indent=2, default=str)

            else:
                # Unknown task type - provide help
                response_content = self._get_help_text()

            # Calculate processing time
            processing_time = (datetime.utcnow() - start_time).total_seconds()

            # Store result in memory
            await self.save_to_memory(
                key=f"last_result_{task_type}",
                value=response_content,
                context=context,
            )

            return AgentResponse(
                agent_name=self.config.name,
                agent_role=self.config.role,
                content=response_content,
                state=AgentState.COMPLETED,
                metadata={
                    "task_type": task_type,
                    "processing_time_seconds": processing_time,
                },
            )

        except Exception as e:
            logger.error(f"JobAnalystAgent processing failed: {e}", exc_info=True)
            return AgentResponse(
                agent_name=self.config.name,
                agent_role=self.config.role,
                content="",
                state=AgentState.FAILED,
                error=str(e),
            )

    async def parse_job_description(
        self,
        context: AgentContext,
        job_description_text: str = "",
        file_path: Optional[str] = None,
        file_content: Optional[str] = None,
    ) -> JDAnalysis:
        """
        Parse a job description into structured data.

        Args:
            context: Agent context
            job_description_text: Raw job description text
            file_path: Path to file containing job description
            file_content: Base64-encoded file content

        Returns:
            JDAnalysis with structured job data
        """
        start_time = datetime.utcnow()

        # Parse file if provided
        if file_path or file_content:
            try:
                file_result = await self.call_tool(
                    "file_parser",
                    {
                        "file_path": file_path,
                        "file_content": file_content,
                        "extract_metadata": True,
                    },
                )
                job_description_text = file_result.get("text", job_description_text)
            except Exception as e:
                logger.warning(f"File parsing failed, using text input: {e}")

        # Use LLM to extract structured data
        llm_response = await self.llm_generate(
            f"{self.JD_PROMPT}\n\nJob Description:\n{job_description_text}",
            context,
            temperature=0.1,  # Very low temperature for parsing
            response_format={"type": "json_object"},
        )

        # Parse LLM response
        try:
            extracted_data = self._clean_and_parse_json(llm_response)

            # Build JobDescription model
            jd = JobDescription(
                title=extracted_data.get("title", "Unknown Position"),
                company=extracted_data.get("company"),
                location=extracted_data.get("location"),
                work_location=WorkLocation(extracted_data.get("work_location", "on_site")),
                employment_type=EmploymentType(extracted_data.get("employment_type", "full_time")),
                experience_level=ExperienceLevel(extracted_data.get("experience_level", "mid")),
                years_of_experience=extracted_data.get("years_of_experience"),
                required_skills=self._parse_skills(extracted_data.get("required_skills", [])),
                preferred_skills=self._parse_skills(extracted_data.get("preferred_skills", [])),
                responsibilities=extracted_data.get("responsibilities", []),
                requirements=extracted_data.get("requirements", []),
                benefits=extracted_data.get("benefits", []),
                salary_min=extracted_data.get("salary_min"),
                salary_max=extracted_data.get("salary_max"),
                salary_currency=extracted_data.get("salary_currency", "USD"),
                description_text=job_description_text,
            )

            # Generate insights
            insights = await self._generate_jd_insights(jd, context)

            # Create analysis result
            processing_time = (datetime.utcnow() - start_time).total_seconds()

            result = JDAnalysis(
                analysis_id=str(uuid.uuid4()),
                session_id=context.session_id,
                job_description=jd,
                llm_model=self.config.model_alias,
                processing_time_seconds=processing_time,
                key_requirements=insights["key_requirements"],
                deal_breakers=insights["deal_breakers"],
                nice_to_haves=insights["nice_to_haves"],
            )

            # Store in memory
            await self.save_to_memory("last_jd_analysis", result.dict(), context)

            logger.info(
                f"Parsed job description: {jd.title} at {jd.company or 'Unknown company'}"
            )
            return result

        except Exception as e:
            logger.error(f"Failed to parse job description: {e}", exc_info=True)
            raise

    async def parse_resume(
        self,
        context: AgentContext,
        resume_text: str = "",
        file_path: Optional[str] = None,
        file_content: Optional[str] = None,
    ) -> ResumeAnalysis:
        """
        Parse a resume into structured data.

        Args:
            context: Agent context
            resume_text: Raw resume text
            file_path: Path to file containing resume
            file_content: Base64-encoded file content

        Returns:
            ResumeAnalysis with structured resume data
        """
        start_time = datetime.utcnow()

        # Parse file if provided
        if file_path or file_content:
            try:
                file_result = await self.call_tool(
                    "file_parser",
                    {
                        "file_path": file_path,
                        "file_content": file_content,
                        "extract_metadata": True,
                    },
                )
                resume_text = file_result.get("text", resume_text)
            except Exception as e:
                logger.warning(f"File parsing failed, using text input: {e}")

        # Use LLM to extract structured data
        llm_response = await self.llm_generate(
            f"{self.RESUME_PROMPT}\n\nResume:\n{resume_text}",
            context,
            temperature=0.1,  # Very low temperature for parsing
            response_format={"type": "json_object"},
        )

        # Parse LLM response
        try:
            extracted_data = self._clean_and_parse_json(llm_response)

            # Calculate total experience
            total_years = self._calculate_total_experience(
                extracted_data.get("work_experience", [])
            )

            # Build Resume model
            resume = Resume(
                name=extracted_data.get("name"),
                email=extracted_data.get("email"),
                phone=extracted_data.get("phone"),
                location=extracted_data.get("location"),
                links=extracted_data.get("links", []),
                summary=extracted_data.get("summary"),
                work_experience=[
                    WorkExperience(**exp) for exp in extracted_data.get("work_experience", [])
                ],
                education=[
                    Education(**edu) for edu in extracted_data.get("education", [])
                ],
                skills=self._parse_skills(extracted_data.get("skills", [])),
                certifications=[
                    Certification(**cert) for cert in extracted_data.get("certifications", [])
                ],
                languages=extracted_data.get("languages", []),
                projects=extracted_data.get("projects", []),
                resume_text=resume_text,
            )

            # Generate insights
            insights = await self._generate_resume_insights(resume, total_years, context)

            # Create analysis result
            processing_time = (datetime.utcnow() - start_time).total_seconds()

            result = ResumeAnalysis(
                analysis_id=str(uuid.uuid4()),
                session_id=context.session_id,
                resume=resume,
                llm_model=self.config.model_alias,
                processing_time_seconds=processing_time,
                key_strengths=insights["strengths"],
                areas_for_improvement=insights["improvements"],
                suggested_roles=insights["suggested_roles"],
                total_years_experience=total_years,
            )

            # Store in memory
            await self.save_to_memory("last_resume_analysis", result.dict(), context)

            logger.info(f"Parsed resume for: {resume.name or 'Unknown candidate'}")
            return result

        except Exception as e:
            logger.error(f"Failed to parse resume: {e}", exc_info=True)
            raise

    async def analyze_match(
        self,
        context: AgentContext,
        job_description: Optional[Dict[str, Any]] = None,
        resume: Optional[Dict[str, Any]] = None,
    ) -> RecruitmentAnalysis:
        """
        Analyze the match between a job description and a resume.

        Args:
            context: Agent context
            job_description: Structured job description data (or will load from memory)
            resume: Structured resume data (or will load from memory)

        Returns:
            RecruitmentAnalysis with match results
        """
        start_time = datetime.utcnow()

        # Load from memory if not provided
        if job_description is None:
            job_description = await self.load_from_memory("last_jd_analysis", context)
        if resume is None:
            resume = await self.load_from_memory("last_resume_analysis", context)

        if not job_description:
            raise ValueError("Job description data required")
        if not resume:
            raise ValueError("Resume data required")

        # Build matching prompt
        jd_for_matching = job_description.get("job_description", job_description)
        resume_for_matching = resume.get("resume", resume)

        # Extract skill names for display
        jd_required = [s.get('name', s) if isinstance(s, dict) else s for s in jd_for_matching.get('required_skills', [])]
        jd_preferred = [s.get('name', s) if isinstance(s, dict) else s for s in jd_for_matching.get('preferred_skills', [])]
        resume_skills = [s.get('name', s) if isinstance(s, dict) else s for s in resume_for_matching.get('skills', [])]

        match_prompt = f"""{self.MATCHING_PROMPT}

Job Description:
Title: {jd_for_matching.get('title', 'Unknown')}
Company: {jd_for_matching.get('company', 'Unknown')}
Required Skills: {jd_required}
Preferred Skills: {jd_preferred}
Experience Level: {jd_for_matching.get('experience_level', 'mid')}
Years Required: {jd_for_matching.get('years_of_experience', 'Not specified')}

Resume:
Name: {resume_for_matching.get('name', 'Unknown')}
Skills: {resume_skills}
Experience: {len(resume_for_matching.get('work_experience', []))} positions
Total Years: {resume.get('total_years_experience', 'Unknown')}

Education: {resume_for_matching.get('education', [])}

Provide the match analysis as JSON."""

        # Get LLM analysis
        llm_response = await self.llm_generate(
            match_prompt,
            context,
            temperature=0.2,
            response_format={"type": "json_object"},
        )

        # Parse match analysis
        try:
            match_data = self._clean_and_parse_json(llm_response)

            # Build skill matches
            skill_matches = self._build_skill_matches(
                jd_for_matching.get("required_skills", []),
                jd_for_matching.get("preferred_skills", []),
                resume_for_matching.get("skills", []),
            )

            # Build match analysis
            match_analysis = MatchAnalysis(
                overall_score=match_data.get("overall_score", 0),
                skill_matches=skill_matches,
                skill_score=match_data.get("skill_score", 0),
                experience_match=match_data.get("experience_match", False),
                experience_note=match_data.get("experience_note", ""),
                education_match=match_data.get("education_match", False),
                education_note=match_data.get("education_note", ""),
                missing_required_skills=match_data.get("missing_required_skills", []),
                missing_preferred_skills=match_data.get("missing_preferred_skills", []),
                additional_skills=match_data.get("additional_skills", []),
                strengths=match_data.get("strengths", []),
                weaknesses=match_data.get("weaknesses", []),
                recommendations=match_data.get("recommendations", []),
            )

            # Generate additional insights
            insights = await self._generate_match_insights(match_analysis, context)

            # Create final result
            processing_time = (datetime.utcnow() - start_time).total_seconds()

            result = RecruitmentAnalysis(
                analysis_id=str(uuid.uuid4()),
                session_id=context.session_id,
                job_description_id=str(job_description.get("analysis_id", "")),
                resume_id=str(resume.get("analysis_id", "")),
                job_description=JobDescription(**jd_for_matching) if isinstance(jd_for_matching, dict) else jd_for_matching,
                resume=Resume(**resume_for_matching) if isinstance(resume_for_matching, dict) else resume_for_matching,
                match_analysis=match_analysis,
                llm_model=self.config.model_alias,
                processing_time_seconds=processing_time,
                insights=insights["insights"],
                red_flags=insights["red_flags"],
            )

            # Store in memory
            await self.save_to_memory("last_match_analysis", result.dict(), context)

            logger.info(
                f"Match analysis complete: {result.match_analysis.overall_score}% match"
            )
            return result

        except Exception as e:
            logger.error(f"Failed to analyze match: {e}", exc_info=True)
            raise

    # ============================================================
    # A2A PROTOCOL HANDLERS
    # ============================================================

    async def handle_a2a_request(self, message: A2AMessage) -> A2AMessage:
        """
        Handle incoming A2A protocol request.

        Args:
            message: A2A message

        Returns:
            A2A response message
        """
        if not message.task:
            return self._a2a.create_response(
                message,
                status_code=self._a2a.status.BAD_REQUEST,
                status_message="No task data in message",
            )

        task_type = message.task.type
        handler = self._a2a_handlers.get(task_type)

        if not handler:
            return self._a2a.create_response(
                message,
                status_code=self._a2a.status.NOT_FOUND,
                status_message=f"Unknown task type: {task_type}",
            )

        try:
            # Create context from A2A message
            context = AgentContext(
                session_id=message.header.conversation_id or "a2a_session",
            )

            # Execute handler
            result = await handler(message.task.data, context)

            # Return A2A response
            return self._a2a.create_response(
                message,
                output_data=result.dict() if hasattr(result, "dict") else result,
                output_type=task_type + "_result",
            )

        except Exception as e:
            logger.error(f"A2A request handler failed: {e}", exc_info=True)
            return self._a2a.create_response(
                message,
                status_code=self._a2a.status.INTERNAL_ERROR,
                status_message=str(e),
            )

    async def _handle_parse_jd(self, data: Dict[str, Any], context: AgentContext) -> JDAnalysis:
        """A2A handler for parsing job descriptions."""
        return await self.parse_job_description(
            context=context,
            job_description_text=data.get("job_description_text", ""),
            file_path=data.get("file_path"),
            file_content=data.get("file_content"),
        )

    async def _handle_parse_resume(self, data: Dict[str, Any], context: AgentContext) -> ResumeAnalysis:
        """A2A handler for parsing resumes."""
        return await self.parse_resume(
            context=context,
            resume_text=data.get("resume_text", ""),
            file_path=data.get("file_path"),
            file_content=data.get("file_content"),
        )

    async def _handle_match_analysis(self, data: Dict[str, Any], context: AgentContext) -> RecruitmentAnalysis:
        """A2A handler for match analysis."""
        return await self.analyze_match(
            context=context,
            job_description=data.get("job_description"),
            resume=data.get("resume"),
        )

    async def _handle_health_check(self, data: Dict[str, Any], context: AgentContext) -> Dict[str, Any]:
        """A2A health check handler."""
        return {
            "status": "healthy",
            "agent": self.config.name,
            "role": self.config.role.value,
            "model": self.config.model_alias,
            "timestamp": datetime.utcnow().isoformat(),
        }

    # ============================================================
    # HELPER METHODS
    # ============================================================

    def _clean_and_parse_json(self, response: str) -> Dict[str, Any]:
        """
        Clean and parse JSON from LLM response.

        LLMs sometimes add markdown formatting or other text around JSON.
        This extracts valid JSON.

        Args:
            response: Raw LLM response text

        Returns:
            Parsed JSON dict
        """
        # Try direct parse first
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Try extracting JSON from markdown code blocks
        if "```json" in response:
            json_part = response.split("```json")[1].split("```")[0].strip()
            return json.loads(json_part)
        elif "```" in response:
            json_part = response.split("```")[1].split("```")[0].strip()
            return json.loads(json_part)

        # Try finding first { and last }
        first_brace = response.find("{")
        last_brace = response.rfind("}")
        if first_brace >= 0 and last_brace > first_brace:
            json_part = response[first_brace:last_brace + 1]
            return json.loads(json_part)

        raise ValueError("Could not extract valid JSON from LLM response")

    def _parse_skills(self, skills_data: List[Any]) -> List[Skill]:
        """
        Parse skills from various formats.

        Args:
            skills_data: Skills in various formats (strings, dicts, etc.)

        Returns:
            List of Skill objects
        """
        skills = []
        for s in skills_data:
            if isinstance(s, str):
                skills.append(Skill(name=s, required=True))
            elif isinstance(s, dict):
                skills.append(Skill(
                    name=s.get("name", ""),
                    category=s.get("category"),
                    required=s.get("required", True),
                    proficiency_level=s.get("proficiency_level"),
                ))
            elif hasattr(s, "name"):  # Pydantic model
                skills.append(Skill(
                    name=s.name,
                    category=getattr(s, "category", None),
                    required=getattr(s, "required", True),
                    proficiency_level=getattr(s, "proficiency_level", None),
                ))
        return skills

    def _calculate_total_experience(self, work_experience: List[Dict[str, Any]]) -> float:
        """
        Calculate total years of experience from work history.

        Args:
            work_experience: List of work experience entries

        Returns:
            Total years of experience
        """
        total_years = 0.0
        for exp in work_experience:
            start_date = exp.get("start_date")
            end_date = exp.get("end_date")
            current = exp.get("current", False)

            if not start_date:
                continue

            try:
                # Parse dates - handle various formats
                if isinstance(start_date, str):
                    start_year = int(start_date[:4]) if start_date[:4].isdigit() else 0
                else:
                    start_year = 0

                if current:
                    end_year = datetime.utcnow().year
                elif end_date and isinstance(end_date, str):
                    end_year = int(end_date[:4]) if end_date[:4].isdigit() else start_year
                else:
                    end_year = start_year

                total_years += max(0, end_year - start_year)
            except (ValueError, TypeError):
                continue

        return round(total_years, 1)

    def _build_skill_matches(
        self,
        required_skills: List[Any],
        preferred_skills: List[Any],
        candidate_skills: List[Any],
    ) -> List[Dict[str, Any]]:
        """
        Build skill match analysis.

        Args:
            required_skills: Required job skills
            preferred_skills: Preferred job skills
            candidate_skills: Candidate's skills

        Returns:
            List of skill match dicts
        """
        # Normalize candidate skills to set
        candidate_skill_names = set()
        for s in candidate_skills:
            if isinstance(s, str):
                candidate_skill_names.add(s.lower())
            elif isinstance(s, dict):
                candidate_skill_names.add(s.get("name", "").lower())
            elif hasattr(s, "name"):
                candidate_skill_names.add(s.name.lower())

        matches = []

        # Check required skills
        for skill in required_skills:
            skill_name = skill if isinstance(skill, str) else skill.get("name", skill)
            skill_name_lower = skill_name.lower()
            matches.append({
                "skill": skill_name,
                "in_job": True,
                "in_resume": skill_name_lower in candidate_skill_names,
                "match_quality": "exact" if skill_name_lower in candidate_skill_names else "missing",
            })

        # Check preferred skills
        for skill in preferred_skills:
            skill_name = skill if isinstance(skill, str) else skill.get("name", skill)
            skill_name_lower = skill_name.lower()
            matches.append({
                "skill": skill_name,
                "in_job": True,
                "in_resume": skill_name_lower in candidate_skill_names,
                "match_quality": "exact" if skill_name_lower in candidate_skill_names else "missing",
            })

        return matches

    async def _generate_jd_insights(
        self,
        jd: JobDescription,
        context: AgentContext,
    ) -> Dict[str, List[str]]:
        """Generate insights from job description."""
        prompt = f"""Analyze this job description and provide:
1. Key requirements (3-5 items)
2. Deal breakers (3-5 items that would disqualify candidates)
3. Nice-to-haves (3-5 bonus qualifications)

Job: {jd.title} at {jd.company or 'Unknown'}

Respond with JSON: {{"key_requirements": [], "deal_breakers": [], "nice_to_haves": []}}"""

        response = await self.llm_generate(prompt, context, temperature=0.3)
        try:
            return self._clean_and_parse_json(response)
        except:
            return {
                "key_requirements": [f"Experience for {jd.title}"],
                "deal_breakers": [],
                "nice_to_haves": [],
            }

    async def _generate_resume_insights(
        self,
        resume: Resume,
        total_years: float,
        context: AgentContext,
    ) -> Dict[str, List[str]]:
        """Generate insights from resume."""
        prompt = f"""Analyze this candidate profile and provide:
1. Key strengths (3-5 items)
2. Areas for improvement (2-3 items)
3. Suggested job roles (3-5 titles that fit)

Candidate: {resume.name or 'Unknown'}
Experience: {total_years} years
Skills: {[s.name for s in resume.skills[:10]]}

Respond with JSON: {{"strengths": [], "improvements": [], "suggested_roles": []}}"""

        response = await self.llm_generate(prompt, context, temperature=0.3)
        try:
            return self._clean_and_parse_json(response)
        except:
            return {
                "strengths": ["Professional experience"],
                "improvements": [],
                "suggested_roles": [],
            }

    async def _generate_match_insights(
        self,
        match_analysis: MatchAnalysis,
        context: AgentContext,
    ) -> Dict[str, List[str]]:
        """Generate additional match insights."""
        prompt = f"""Based on this match analysis ({match_analysis.overall_score}% match),
provide 3-5 additional insights for the hiring team.

Focus on: interview topics, concerns to probe, potential red flags.

Respond with JSON: {{"insights": [], "red_flags": []}}"""

        response = await self.llm_generate(prompt, context, temperature=0.3)
        try:
            return self._clean_and_parse_json(response)
        except:
            return {"insights": [], "red_flags": []}

    def _get_help_text(self) -> str:
        """Get help text for unknown task types."""
        return """JobAnalystAgent - Recruitment Document Analysis

Supported task types:

1. parse_jd - Parse job description
   Input: job_description_text or file_path/file_content

2. parse_resume - Parse resume/CV
   Input: resume_text or file_path/file_content

3. match_analysis - Analyze job-resume fit
   Input: job_description (dict), resume (dict)

Example:
{
    "task_type": "parse_jd",
    "job_description_text": "Senior Software Engineer..."
}

Memory Scoping:
- All analyses are stored in session-scoped memory
- Use session_id to maintain context across requests
- Previous analyses can be referenced by task type

A2A Protocol:
- Agent accepts A2A messages on /a2a endpoint
- Supported A2A task types: parse_jd, parse_resume, match_analysis, health_check
"""


# ============================================================
# FACTORY FUNCTION
# ============================================================

def create_job_analyst_agent(
    name: str = "job_analyst",
    model_alias: str = "analyst-agent",
    **config_kwargs,
) -> JobAnalystAgent:
    """
    Factory function to create a configured JobAnalystAgent.

    Args:
        name: Agent name
        model_alias: LiteLLM model alias
        **config_kwargs: Additional configuration

    Returns:
        Configured JobAnalystAgent instance
    """
    from .tools import ToolFactory

    # Create agent configuration
    config = AgentConfig(
        name=name,
        role=AgentRole.ANALYST,
        model_alias=model_alias,
        temperature=0.2,
        **config_kwargs,
    )

    # Create tools for the agent
    tools = [
        ToolFactory.get_file_parser().to_definition(),
        ToolFactory.get_database_reader().to_definition(),
        ToolFactory.get_database_writer().to_definition(),
    ]

    # Create agent instance
    agent = JobAnalystAgent(config=config)
    for tool in tools:
        agent.register_tool(tool)

    logger.info(f"Created JobAnalystAgent: {name} with model {model_alias}")
    return agent
