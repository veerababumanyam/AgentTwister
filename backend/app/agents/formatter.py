"""
Formatter Agent

Specialized agent for output polishing, documentation generation, and report formatting.
Assembles final documents, generates payload manifests, creates preview artifacts,
and prepares evidence bundles for authorized security testing.

This agent is designed for security research workflows:
- Format findings into professional documents
- Generate payload manifests and documentation
- Create preview artifacts for testing
- Assemble evidence bundles with full provenance
- Export to multiple formats (DOCX, PDF, JSON, Markdown)
- Ensure consistent formatting across all outputs
"""

import json
import logging
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from ..models.plan import AttackPlan, AttackStep, PlanStatus
from ..models.payload import PayloadTemplate, StealthTechnique, DocumentTemplate
from ..models.evidence_bundle import EvidenceBundle
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
    A2AMessage,
    A2AStatusCode,
)

logger = logging.getLogger(__name__)


class OutputFormat(str, Enum):
    """Supported output formats for documents."""

    DOCX = "docx"
    PDF = "pdf"
    MARKDOWN = "markdown"
    HTML = "html"
    JSON = "json"
    TXT = "txt"


class ReportType(str, Enum):
    """Types of reports that can be generated."""

    FINDINGS_REPORT = "findings_report"
    EXECUTION_SUMMARY = "execution_summary"
    TECHNICAL_DETAILS = "technical_details"
    PAYLOAD_MANIFEST = "payload_manifest"
    EVIDENCE_BUNDLE = "evidence_bundle"
    FINAL_REPORT = "final_report"
    INTERIM_REPORT = "interim_report"


class FormattedDocument(BaseModel):
    """A formatted document ready for export."""

    document_id: str = Field(default_factory=lambda: str(uuid4()))
    document_type: ReportType
    output_format: OutputFormat

    # Content
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., description="Main document content")
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # Structure
    sections: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Document sections with titles and content"
    )

    # Styling
    template: Optional[str] = Field(None, description="Template used for formatting")

    # File information
    filename: Optional[str] = Field(None, description="Suggested filename")
    file_size_bytes: Optional[int] = Field(None, description="Size of generated file")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    generated_by: str = Field(default="formatter")


class PayloadManifestItem(BaseModel):
    """A single item in a payload manifest."""

    payload_id: str
    name: str
    category: str
    template: str
    rendered_payload: str
    stealth_technique: Optional[str] = None

    # Placement information
    document_id: Optional[str] = None
    document_type: Optional[str] = None
    placement_location: Optional[str] = None

    # Status
    status: str = Field(default="ready")
    reviewed: bool = Field(default=False)
    approved: bool = Field(default=False)

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    notes: List[str] = Field(default_factory=list)


class PayloadManifest(BaseModel):
    """Complete manifest of all payloads in a campaign."""

    manifest_id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str
    campaign_id: Optional[str] = None

    # Manifest information
    title: str = Field(..., min_length=1)
    description: str = Field(default="")
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    # Payloads
    payloads: List[PayloadManifestItem] = Field(default_factory=list)

    # Summary
    total_payloads: int = Field(default=0)
    by_status: Dict[str, int] = Field(default_factory=dict)
    by_category: Dict[str, int] = Field(default_factory=dict)

    # Export
    export_formats: List[OutputFormat] = Field(
        default_factory=lambda: [OutputFormat.JSON, OutputFormat.MARKDOWN]
    )

    def calculate_summaries(self) -> None:
        """Calculate summary statistics."""
        self.total_payloads = len(self.payloads)

        # Count by status
        for payload in self.payloads:
            status = payload.status
            self.by_status[status] = self.by_status.get(status, 0) + 1

            category = payload.category
            self.by_category[category] = self.by_category.get(category, 0) + 1


class FormattedReport(BaseModel):
    """A complete formatted report with all sections."""

    report_id: str = Field(default_factory=lambda: str(uuid4()))
    report_type: ReportType
    session_id: str
    plan_id: Optional[str] = None

    # Report metadata
    title: str = Field(..., min_length=1, max_length=200)
    subtitle: Optional[str] = None
    author: str = Field(default="AgentTwister Security Research")
    version: str = Field(default="1.0.0")

    # Content sections
    executive_summary: Optional[str] = None
    introduction: Optional[str] = None
    methodology: Optional[str] = None
    findings: List[Dict[str, Any]] = Field(default_factory=list)
    technical_details: List[Dict[str, Any]] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    conclusion: Optional[str] = None

    # Appendices
    payload_manifest: Optional[PayloadManifest] = None
    evidence_references: List[str] = Field(default_factory=list)
    compliance_mappings: Dict[str, List[str]] = Field(default_factory=dict)

    # Formatting
    template: str = Field(default="standard")
    include_toc: bool = Field(default=True)
    include_page_numbers: bool = Field(default=True)

    # Export options
    export_formats: List[OutputFormat] = Field(
        default_factory=lambda: [OutputFormat.PDF, OutputFormat.DOCX]
    )

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_modified: datetime = Field(default_factory=datetime.utcnow)

    # Statistics
    total_findings: int = Field(default=0)
    critical_findings: int = Field(default=0)
    high_findings: int = Field(default=0)
    medium_findings: int = Field(default=0)
    low_findings: int = Field(default=0)

    def calculate_statistics(self) -> None:
        """Calculate report statistics."""
        self.total_findings = len(self.findings)

        for finding in self.findings:
            severity = finding.get("severity", "low").lower()
            if severity == "critical":
                self.critical_findings += 1
            elif severity == "high":
                self.high_findings += 1
            elif severity == "medium":
                self.medium_findings += 1
            elif severity == "low":
                self.low_findings += 1


class FormatterAgent(BaseAgent):
    """
    Formatter Agent - Output polishing and documentation generation.

    This agent specializes in creating professional security research deliverables:
    - Formats findings into structured reports
    - Generates payload manifests with full documentation
    - Creates preview artifacts for testing
    - Assembles evidence bundles with provenance
    - Exports to multiple formats (DOCX, PDF, JSON, Markdown)
    - Ensures consistent formatting and branding
    - Maintains document templates and styles

    The Formatter is the final step in the pipeline:
    - Receives: Results from all previous agents
    - Produces: Professional deliverables for stakeholders

    Integration:
    - Uses LiteLLM with model alias "formatter-agent"
    - Cost-optimized model (GPT-4o-mini) for formatting tasks
    - No long-term memory needed (stateless formatter)
    - Provides A2A Protocol-compliant communication
    - No external tools needed (generates documents internally)
    """

    # System prompts for different formatting tasks
    REPORT_GENERATION_PROMPT = """You are an expert at writing professional security research reports.

Your task is to generate a well-structured report section based on the provided information.

Guidelines:
1. Use clear, professional language
2. Maintain appropriate tone for security documentation
3. Include sufficient technical detail
4. Follow standard report structure
5. Ensure clarity and readability

Generate content that is:
- Professional and authoritative
- Clear and concise
- Technically accurate
- Appropriate for the intended audience

Respond with well-formatted text content."""

    SUMMARY_GENERATION_PROMPT = """You are an expert at creating executive summaries for security assessments.

Create a concise executive summary (2-3 paragraphs) that:
1. States the purpose and scope of the assessment
2. Highlights key findings (critical and high severity)
3. Provides overall risk assessment
4. Includes actionable next steps

The summary should be understandable by non-technical stakeholders while
maintaining accuracy and completeness."""

    FINDINGS_FORMAT_PROMPT = """You are an expert at formatting security findings for professional reports.

Format the provided findings with:
1. Clear severity ratings
2. Concise descriptions
3. Impact assessments
4. Reproducibility information
5. Evidence references

Each finding should include:
- Finding ID and title
- Severity and category
- Description and impact
- Steps to reproduce
- Evidence references
- Recommendations

Format findings consistently with clear structure."""

    MANIFEST_GENERATION_PROMPT = """You are an expert at creating payload manifests for security testing documentation.

Create a comprehensive manifest that:
1. Lists all payloads with unique identifiers
2. Categorizes by attack type
3. Documents stealth techniques used
4. Includes rendering instructions
5. Provides provenance and approval status

The manifest should enable:
- Complete traceability of each payload
- Easy reproduction of tests
- Clear audit trail
- Compliance documentation"""

    def __init__(self, config: Optional[AgentConfig] = None):
        """
        Initialize the Formatter Agent.

        Args:
            config: Optional agent configuration. Uses defaults if not provided.
        """
        if config is None:
            config = AgentConfig(
                name="formatter",
                role=AgentRole.FORMATTER,
                model_alias="formatter-agent",
                temperature=0.5,  # Balanced temperature for creative formatting
                max_tokens=4096,
                enable_long_term_memory=False,  # No long-term memory needed
                memory_collection="formatter_memories",
            )
        super().__init__(config)

        # Initialize A2A protocol adapter for inter-agent communication
        self._a2a = A2AProtocolAdapter(
            config=A2AConfig(
                agent_name="formatter",
                agent_role="formatter",
                agent_version="1.0.0",
            ),
        )

        # Register A2A message handlers
        self._register_a2a_handlers()

        # Document templates
        self._templates = self._load_templates()

        logger.info("FormatterAgent initialized with A2A protocol support")

    def _register_a2a_handlers(self) -> None:
        """Register A2A protocol message handlers."""
        self._a2a_handlers = {
            "format_report": self._handle_format_report,
            "generate_manifest": self._handle_generate_manifest,
            "create_document": self._handle_create_document,
            "export_evidence": self._handle_export_evidence,
            "format_findings": self._handle_format_findings,
            "generate_summary": self._handle_generate_summary,
            "health_check": self._handle_health_check,
        }

    def _load_templates(self) -> Dict[str, str]:
        """Load document templates."""
        return {
            "standard": """
# {{title}}

{{subtitle}}

Generated by {{author}} on {{date}}

---

## Table of Contents

{{toc}}

---

{{content}}

---

*This report was generated by AgentTwister for authorized security testing purposes.*
""",
            "findings_report": """
# Security Findings Report

**Target:** {{target_system}}
**Assessment Date:** {{date}}
**Report ID:** {{report_id}}

## Executive Summary

{{executive_summary}}

## Findings Summary

{{findings_summary}}

## Detailed Findings

{{findings}}

## Recommendations

{{recommendations}}

---

*Report generated by AgentTwister - AI Security Testing Platform*
""",
            "payload_manifest": """
# Payload Manifest

**Session:** {{session_id}}
**Generated:** {{date}}

## Overview

This manifest documents all payloads generated for the authorized security test.

## Payloads

{{payloads}}

## Provenance

{{provenance}}

---

*Manifest generated by AgentTwister*
""",
        }

    async def process(
        self,
        context: AgentContext,
        input_data: Dict[str, Any],
    ) -> AgentResponse:
        """
        Process the agent's main task.

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
            if task_type == "format_report":
                result = await self.format_report(
                    context=context,
                    plan_data=input_data.get("plan_data"),
                    findings=input_data.get("findings", []),
                    report_type=input_data.get("report_type", ReportType.FINDINGS_REPORT),
                    options=input_data.get("options", {}),
                )
                response_content = json.dumps(result.dict(), indent=2, default=str)

            elif task_type == "generate_manifest":
                result = await self.generate_payload_manifest(
                    context=context,
                    payloads=input_data.get("payloads", []),
                    metadata=input_data.get("metadata", {}),
                )
                response_content = json.dumps(result.dict(), indent=2, default=str)

            elif task_type == "create_document":
                result = await self.create_document(
                    context=context,
                    document_type=input_data.get("document_type", ReportType.FINDINGS_REPORT),
                    content=input_data.get("content", {}),
                    output_format=input_data.get("output_format", OutputFormat.MARKDOWN),
                    template=input_data.get("template"),
                )
                response_content = json.dumps(result.dict(), indent=2, default=str)

            elif task_type == "export_evidence":
                result = await self.export_evidence_bundle(
                    context=context,
                    plan_id=input_data.get("plan_id"),
                    include_payloads=input_data.get("include_payloads", True),
                    include_findings=input_data.get("include_findings", True),
                    output_format=input_data.get("output_format", OutputFormat.JSON),
                )
                response_content = json.dumps(result.dict(), indent=2, default=str)

            elif task_type == "format_findings":
                result = await self.format_findings(
                    context=context,
                    findings=input_data.get("findings", []),
                    format_style=input_data.get("format_style", "standard"),
                )
                response_content = json.dumps(result, indent=2, default=str)

            elif task_type == "generate_summary":
                result = await self.generate_summary(
                    context=context,
                    plan_data=input_data.get("plan_data"),
                    findings=input_data.get("findings", []),
                )
                response_content = json.dumps({"summary": result}, indent=2)

            elif task_type == "get_document":
                result = await self.get_document(
                    context=context,
                    document_id=input_data.get("document_id"),
                )
                if result:
                    response_content = json.dumps(result.dict(), indent=2, default=str)
                else:
                    response_content = '{"error": "Document not found"}'

            elif task_type == "list_documents":
                result = await self.list_documents(context=context)
                response_content = json.dumps(
                    [d.dict() if hasattr(d, "dict") else d for d in result],
                    indent=2,
                    default=str
                )

            else:
                # Unknown task type - provide help
                response_content = self._get_help_text()

            # Calculate processing time
            processing_time = (datetime.utcnow() - start_time).total_seconds()

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
            logger.error(f"FormatterAgent processing failed: {e}", exc_info=True)
            return AgentResponse(
                agent_name=self.config.name,
                agent_role=self.config.role,
                content="",
                state=AgentState.FAILED,
                error=str(e),
            )

    async def format_report(
        self,
        context: AgentContext,
        plan_data: Dict[str, Any],
        findings: List[Dict[str, Any]],
        report_type: ReportType,
        options: Dict[str, Any],
    ) -> FormattedReport:
        """
        Generate a complete formatted report.

        Args:
            context: Agent context
            plan_data: Attack plan data
            findings: List of security findings
            report_type: Type of report to generate
            options: Additional formatting options

        Returns:
            Complete FormattedReport ready for export
        """
        # Create report structure
        report = FormattedReport(
            report_type=report_type,
            session_id=context.session_id,
            plan_id=plan_data.get("plan_id"),
            title=options.get("title", self._generate_title(plan_data, report_type)),
            subtitle=options.get("subtitle"),
        )

        # Generate executive summary
        report.executive_summary = await self.generate_summary(
            context=context,
            plan_data=plan_data,
            findings=findings,
        )

        # Generate introduction
        report.introduction = await self._generate_introduction(
            plan_data=plan_data,
            context=context,
        )

        # Generate methodology
        report.methodology = await self._generate_methodology(
            plan_data=plan_data,
            context=context,
        )

        # Format findings
        formatted_findings = await self.format_findings(
            context=context,
            findings=findings,
            format_style=options.get("format_style", "standard"),
        )
        report.findings = formatted_findings

        # Generate technical details
        report.technical_details = await self._generate_technical_details(
            plan_data=plan_data,
            context=context,
        )

        # Generate recommendations
        report.recommendations = await self._generate_recommendations(
            findings=findings,
            context=context,
        )

        # Generate conclusion
        report.conclusion = await self._generate_conclusion(
            plan_data=plan_data,
            findings=findings,
            context=context,
        )

        # Add compliance mappings
        report.compliance_mappings = self._generate_compliance_mappings(
            plan_data=plan_data,
        )

        # Calculate statistics
        report.calculate_statistics()

        # Store in memory
        await self.save_to_memory(
            key=f"report_{report.report_id}",
            value=report.dict(),
            context=context,
        )

        # Add to documents index
        await self._add_to_documents_index(report.report_id, context)

        logger.info(
            f"Generated formatted report '{report.report_id}' "
            f"of type '{report_type.value}' with {report.total_findings} findings"
        )
        return report

    async def generate_payload_manifest(
        self,
        context: AgentContext,
        payloads: List[Dict[str, Any]],
        metadata: Dict[str, Any],
    ) -> PayloadManifest:
        """
        Generate a payload manifest.

        Args:
            context: Agent context
            payloads: List of payloads to document
            metadata: Additional metadata

        Returns:
            Complete PayloadManifest
        """
        manifest = PayloadManifest(
            session_id=context.session_id,
            campaign_id=metadata.get("campaign_id"),
            title=metadata.get("title", "Payload Manifest"),
            description=metadata.get("description", ""),
        )

        # Add payloads to manifest
        for payload_data in payloads:
            item = PayloadManifestItem(
                payload_id=payload_data.get("payload_id", str(uuid.uuid4())),
                name=payload_data.get("name", "Unnamed Payload"),
                category=payload_data.get("category", "Unknown"),
                template=payload_data.get("template", ""),
                rendered_payload=payload_data.get("content", ""),
                stealth_technique=payload_data.get("stealth_technique"),
                document_id=payload_data.get("document_id"),
                document_type=payload_data.get("document_type"),
                placement_location=payload_data.get("placement_location"),
                status=payload_data.get("status", "ready"),
                reviewed=payload_data.get("reviewed", False),
                approved=payload_data.get("approved", False),
                notes=payload_data.get("notes", []),
            )
            manifest.payloads.append(item)

        # Calculate summaries
        manifest.calculate_summaries()

        # Store in memory
        await self.save_to_memory(
            key=f"manifest_{manifest.manifest_id}",
            value=manifest.dict(),
            context=context,
        )

        logger.info(
            f"Generated payload manifest '{manifest.manifest_id}' "
            f"with {manifest.total_payloads} payloads"
        )
        return manifest

    async def create_document(
        self,
        context: AgentContext,
        document_type: ReportType,
        content: Dict[str, Any],
        output_format: OutputFormat,
        template: Optional[str],
    ) -> FormattedDocument:
        """
        Create a formatted document.

        Args:
            context: Agent context
            document_type: Type of document
            content: Document content
            output_format: Desired output format
            template: Template to use

        Returns:
            FormattedDocument ready for export
        """
        # Generate document content using template
        if template and template in self._templates:
            document_content = self._apply_template(
                template=template,
                content=content,
            )
        else:
            # Use LLM to generate content
            document_content = await self._generate_document_content(
                document_type=document_type,
                content=content,
                context=context,
            )

        # Create document
        document = FormattedDocument(
            document_type=document_type,
            output_format=output_format,
            title=content.get("title", f"{document_type.value}"),
            content=document_content,
            metadata=content.get("metadata", {}),
            sections=content.get("sections", []),
            template=template,
            filename=self._generate_filename(document_type, output_format),
        )

        # Store in memory
        await self.save_to_memory(
            key=f"document_{document.document_id}",
            value=document.dict(),
            context=context,
        )

        # Add to documents index
        await self._add_to_documents_index(document.document_id, context)

        logger.info(
            f"Created document '{document.document_id}' "
            f"of type '{document_type.value}' in format '{output_format.value}'"
        )
        return document

    async def export_evidence_bundle(
        self,
        context: AgentContext,
        plan_id: str,
        include_payloads: bool,
        include_findings: bool,
        output_format: OutputFormat,
    ) -> EvidenceBundle:
        """
        Export a complete evidence bundle.

        Args:
            context: Agent context
            plan_id: Plan to bundle evidence for
            include_payloads: Whether to include payload data
            include_findings: Whether to include findings
            output_format: Export format

        Returns:
            Complete EvidenceBundle
        """
        # Load plan data
        plan_data = await self.load_from_memory(f"plan_{plan_id}", context)
        if not plan_data:
            raise ValueError(f"Plan not found: {plan_id}")

        # Create evidence bundle
        bundle = EvidenceBundle(
            bundle_id=str(uuid.uuid4()),
            session_id=context.session_id,
            plan_id=plan_id,
            target_system=plan_data.get("target_system", "Unknown"),
        )

        # Add payloads if requested
        if include_payloads:
            # Load payload manifest if available
            manifest_data = await self.load_from_memory(
                f"manifest_for_plan_{plan_id}",
                context
            )
            if manifest_data:
                bundle.payloads = manifest_data.get("payloads", [])

        # Add findings if requested
        if include_findings:
            findings_data = await self.load_from_memory(
                f"findings_for_plan_{plan_id}",
                context
            )
            if findings_data:
                bundle.findings = findings_data

        # Add metadata
        bundle.metadata = {
            "exported_at": datetime.utcnow().isoformat(),
            "export_format": output_format.value,
            "includes_payloads": include_payloads,
            "includes_findings": include_findings,
        }

        # Store bundle
        await self.save_to_memory(
            key=f"bundle_{bundle.bundle_id}",
            value=bundle.dict(),
            context=context,
        )

        logger.info(f"Exported evidence bundle '{bundle.bundle_id}'")
        return bundle

    async def format_findings(
        self,
        context: AgentContext,
        findings: List[Dict[str, Any]],
        format_style: str,
    ) -> List[Dict[str, Any]]:
        """
        Format security findings consistently.

        Args:
            context: Agent context
            findings: Raw findings data
            format_style: Style format to apply

        Returns:
            Formatted findings
        """
        if not findings:
            return []

        # Format each finding
        formatted = []
        for finding in findings:
            formatted_finding = {
                "finding_id": finding.get("finding_id", f"FIND-{str(uuid.uuid4())[:8]}"),
                "title": finding.get("title", "Untitled Finding"),
                "severity": finding.get("severity", "medium").upper(),
                "category": finding.get("category", "General"),
                "description": finding.get("description", ""),
                "impact": finding.get("impact", "Not specified"),
                "evidence": finding.get("evidence", []),
                "recommendations": finding.get("recommendations", []),
                "references": finding.get("references", []),
                "discovered_at": finding.get("discovered_at", datetime.utcnow().isoformat()),
            }
            formatted.append(formatted_finding)

        # Optionally use LLM to improve formatting
        if format_style != "raw":
            prompt = f"""{self.FINDINGS_FORMAT_PROMPT}

Findings to format:
{json.dumps(formatted, indent=2)}

Format these findings according to the style guide above.
Respond ONLY with a JSON array of formatted findings."""

            try:
                llm_response = await self.llm_generate(
                    prompt,
                    context,
                    temperature=0.3,
                    response_format={"type": "json_object"},
                )
                result = self._clean_and_parse_json(llm_response)
                if "findings" in result:
                    formatted = result["findings"]
            except Exception as e:
                logger.warning(f"LLM formatting failed, using basic format: {e}")

        return formatted

    async def generate_summary(
        self,
        context: AgentContext,
        plan_data: Dict[str, Any],
        findings: List[Dict[str, Any]],
    ) -> str:
        """
        Generate executive summary.

        Args:
            context: Agent context
            plan_data: Plan information
            findings: Security findings

        Returns:
            Executive summary text
        """
        # Build summary data
        summary_data = {
            "target": plan_data.get("target_system", "Target System"),
            "date": datetime.utcnow().strftime("%Y-%m-%d"),
            "total_findings": len(findings),
            "critical_count": sum(1 for f in findings if f.get("severity") == "critical"),
            "high_count": sum(1 for f in findings if f.get("severity") == "high"),
            "plan_objective": plan_data.get("overall_strategy", "Security assessment"),
        }

        prompt = f"""{self.SUMMARY_GENERATION_PROMPT}

Assessment Information:
{json.dumps(summary_data, indent=2)}

Findings:
{json.dumps(findings[:5], indent=2)}  # Top 5 findings

Generate a concise executive summary (2-3 paragraphs)."""

        return await self.llm_generate(
            prompt,
            context,
            temperature=0.5,
        )

    async def get_document(
        self,
        context: AgentContext,
        document_id: str,
    ) -> Optional[Union[FormattedDocument, FormattedReport, PayloadManifest]]:
        """Retrieve a document by ID."""
        # Try report first
        report_data = await self.load_from_memory(f"report_{document_id}", context)
        if report_data:
            return FormattedReport(**report_data)

        # Try manifest
        manifest_data = await self.load_from_memory(f"manifest_{document_id}", context)
        if manifest_data:
            return PayloadManifest(**manifest_data)

        # Try document
        document_data = await self.load_from_memory(f"document_{document_id}", context)
        if document_data:
            return FormattedDocument(**document_data)

        return None

    async def list_documents(
        self,
        context: AgentContext,
    ) -> List[Dict[str, Any]]:
        """List all documents for the current session."""
        index_data = await self.load_from_memory("documents_index", context)
        if not index_data:
            return []

        document_summaries = []
        for doc_id in index_data.get("document_ids", []):
            doc_data = await self.load_from_memory(f"report_{doc_id}", context)
            if not doc_data:
                doc_data = await self.load_from_memory(f"manifest_{doc_id}", context)
            if not doc_data:
                doc_data = await self.load_from_memory(f"document_{doc_id}", context)

            if doc_data:
                document_summaries.append({
                    "document_id": doc_id,
                    "type": doc_data.get("report_type") or doc_data.get("document_type") or "unknown",
                    "title": doc_data.get("title") or doc_data.get("name") or "Untitled",
                    "created_at": doc_data.get("created_at") or doc_data.get("generated_at"),
                })

        return document_summaries

    # ============================================================
    # A2A PROTOCOL HANDLERS
    # ============================================================

    async def handle_a2a_request(self, message: A2AMessage) -> A2AMessage:
        """Handle incoming A2A protocol request."""
        if not message.task:
            return self._a2a.create_response(
                message,
                status_code=A2AStatusCode.BAD_REQUEST,
                status_message="No task data in message",
            )

        task_type = message.task.type
        handler = self._a2a_handlers.get(task_type)

        if not handler:
            return self._a2a.create_response(
                message,
                status_code=A2AStatusCode.NOT_FOUND,
                status_message=f"Unknown task type: {task_type}",
            )

        try:
            context = AgentContext(
                session_id=message.header.conversation_id or "a2a_session",
            )

            result = await handler(message.task.data, context)

            return self._a2a.create_response(
                message,
                output_data=result.dict() if hasattr(result, "dict") else result,
                output_type=task_type + "_result",
            )

        except Exception as e:
            logger.error(f"A2A request handler failed: {e}", exc_info=True)
            return self._a2a.create_response(
                message,
                status_code=A2AStatusCode.INTERNAL_ERROR,
                status_message=str(e),
            )

    async def _handle_format_report(self, data: Dict[str, Any], context: AgentContext) -> FormattedReport:
        """A2A handler for formatting report."""
        return await self.format_report(
            context=context,
            plan_data=data.get("plan_data"),
            findings=data.get("findings", []),
            report_type=ReportType(data.get("report_type", ReportType.FINDINGS_REPORT)),
            options=data.get("options", {}),
        )

    async def _handle_generate_manifest(self, data: Dict[str, Any], context: AgentContext) -> PayloadManifest:
        """A2A handler for generating manifest."""
        return await self.generate_payload_manifest(
            context=context,
            payloads=data.get("payloads", []),
            metadata=data.get("metadata", {}),
        )

    async def _handle_create_document(self, data: Dict[str, Any], context: AgentContext) -> FormattedDocument:
        """A2A handler for creating document."""
        return await self.create_document(
            context=context,
            document_type=ReportType(data.get("document_type", ReportType.FINDINGS_REPORT)),
            content=data.get("content", {}),
            output_format=OutputFormat(data.get("output_format", OutputFormat.MARKDOWN)),
            template=data.get("template"),
        )

    async def _handle_export_evidence(self, data: Dict[str, Any], context: AgentContext) -> EvidenceBundle:
        """A2A handler for exporting evidence."""
        return await self.export_evidence_bundle(
            context=context,
            plan_id=data.get("plan_id"),
            include_payloads=data.get("include_payloads", True),
            include_findings=data.get("include_findings", True),
            output_format=OutputFormat(data.get("output_format", OutputFormat.JSON)),
        )

    async def _handle_format_findings(self, data: Dict[str, Any], context: AgentContext) -> List[Dict[str, Any]]:
        """A2A handler for formatting findings."""
        return await self.format_findings(
            context=context,
            findings=data.get("findings", []),
            format_style=data.get("format_style", "standard"),
        )

    async def _handle_generate_summary(self, data: Dict[str, Any], context: AgentContext) -> str:
        """A2A handler for generating summary."""
        return await self.generate_summary(
            context=context,
            plan_data=data.get("plan_data"),
            findings=data.get("findings", []),
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
        """Clean and parse JSON from LLM response."""
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

    def _generate_title(self, plan_data: Dict[str, Any], report_type: ReportType) -> str:
        """Generate report title."""
        target = plan_data.get("target_system", "Target System")
        type_suffix = {
            ReportType.FINDINGS_REPORT: "Security Findings Report",
            ReportType.EXECUTION_SUMMARY: "Executive Summary",
            ReportType.TECHNICAL_DETAILS: "Technical Details",
            ReportType.PAYLOAD_MANIFEST: "Payload Manifest",
            ReportType.EVIDENCE_BUNDLE: "Evidence Bundle",
            ReportType.FINAL_REPORT: "Final Assessment Report",
            ReportType.INTERIM_REPORT: "Interim Status Report",
        }
        return f"{target} - {type_suffix.get(report_type, 'Report')}"

    def _generate_filename(self, document_type: ReportType, output_format: OutputFormat) -> str:
        """Generate filename for document."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        ext_map = {
            OutputFormat.DOCX: "docx",
            OutputFormat.PDF: "pdf",
            OutputFormat.MARKDOWN: "md",
            OutputFormat.HTML: "html",
            OutputFormat.JSON: "json",
            OutputFormat.TXT: "txt",
        }
        ext = ext_map.get(output_format, "txt")
        return f"{document_type.value}_{timestamp}.{ext}"

    def _apply_template(self, template: str, content: Dict[str, Any]) -> str:
        """Apply template to content."""
        template_str = self._templates.get(template, template)

        # Replace placeholders
        result = template_str
        for key, value in content.items():
            placeholder = f"{{{{{key}}}}}"
            result = result.replace(placeholder, str(value))

        # Add timestamp
        result = result.replace("{{date}}", datetime.utcnow().strftime("%Y-%m-%d"))
        result = result.replace("{{report_id}}", str(uuid.uuid4())[:8])

        return result

    async def _generate_document_content(
        self,
        document_type: ReportType,
        content: Dict[str, Any],
        context: AgentContext,
    ) -> str:
        """Generate document content using LLM."""
        prompt = f"""{self.REPORT_GENERATION_PROMPT}

Document Type: {document_type.value}

Content to format:
{json.dumps(content, indent=2)}

Generate well-formatted content for this document."""

        return await self.llm_generate(
            prompt,
            context,
            temperature=0.5,
        )

    async def _generate_introduction(
        self,
        plan_data: Dict[str, Any],
        context: AgentContext,
    ) -> str:
        """Generate report introduction."""
        prompt = f"""Generate a professional introduction for a security assessment report.

Target System: {plan_data.get('target_system', 'Not specified')}
Assessment Date: {datetime.utcnow().strftime('%Y-%m-%d')}

Include:
- Purpose of the assessment
- Scope of testing
- Methodology overview
- Disclaimer about authorized testing

Keep it to 2-3 paragraphs."""

        return await self.llm_generate(prompt, context, temperature=0.5)

    async def _generate_methodology(
        self,
        plan_data: Dict[str, Any],
        context: AgentContext,
    ) -> str:
        """Generate methodology section."""
        steps = plan_data.get("attack_steps", [])
        categories = set(step.get("attack_category", "Unknown") for step in steps)

        prompt = f"""Generate a methodology section for a security assessment report.

Testing Categories:
{', '.join(categories)}

Number of Test Cases: {len(steps)}

Describe:
- Testing approach
- Tools and techniques used
- Testing categories covered
- Validation methods

Keep it to 2-3 paragraphs."""

        return await self.llm_generate(prompt, context, temperature=0.5)

    async def _generate_technical_details(
        self,
        plan_data: Dict[str, Any],
        context: AgentContext,
    ) -> List[Dict[str, Any]]:
        """Generate technical details section."""
        details = []
        for step in plan_data.get("attack_steps", []):
            details.append({
                "step": step.get("step_number"),
                "name": step.get("name"),
                "category": step.get("attack_category"),
                "description": step.get("description"),
                "complexity": step.get("complexity"),
                "expected_outcome": step.get("expected_outcome"),
            })
        return details

    async def _generate_recommendations(
        self,
        findings: List[Dict[str, Any]],
        context: AgentContext,
    ) -> List[str]:
        """Generate recommendations based on findings."""
        if not findings:
            return ["No security issues identified. Continue monitoring."]

        # Group findings by severity
        critical = [f for f in findings if f.get("severity") == "critical"]
        high = [f for f in findings if f.get("severity") == "high"]

        recommendations = []

        if critical:
            recommendations.append(
                f"Immediately address {len(critical)} critical finding(s) "
                "to prevent potential security incidents."
            )

        if high:
            recommendations.append(
                f"Prioritize remediation of {len(high)} high-severity finding(s) "
                "within the next maintenance cycle."
            )

        # Add general recommendations
        recommendations.extend([
            "Implement regular security testing for all AI-powered features.",
            "Establish a process for reviewing and updating security controls.",
            "Consider integrating security testing into the CI/CD pipeline.",
        ])

        return recommendations

    async def _generate_conclusion(
        self,
        plan_data: Dict[str, Any],
        findings: List[Dict[str, Any]],
        context: AgentContext,
    ) -> str:
        """Generate report conclusion."""
        total = len(findings)
        critical = sum(1 for f in findings if f.get("severity") == "critical")
        high = sum(1 for f in findings if f.get("severity") == "high")

        prompt = f"""Generate a conclusion for a security assessment report.

Assessment Results:
- Total Findings: {total}
- Critical: {critical}
- High: {high}

Provide:
- Overall risk assessment
- Summary of testing results
- Next steps
- Thank you and contact information

Keep it to 2-3 paragraphs."""

        return await self.llm_generate(prompt, context, temperature=0.5)

    def _generate_compliance_mappings(
        self,
        plan_data: Dict[str, Any],
    ) -> Dict[str, List[str]]:
        """Generate compliance framework mappings."""
        return plan_data.get("framework_mappings", {
            "OWASP AI Security Standard": [],
            "MITRE ATLAS": [],
            "NIST AI RMF": [],
        })

    async def _add_to_documents_index(self, document_id: str, context: AgentContext) -> None:
        """Add document ID to the session's documents index."""
        index_data = await self.load_from_memory("documents_index", context)
        if not index_data:
            index_data = {"document_ids": []}

        if document_id not in index_data["document_ids"]:
            index_data["document_ids"].append(document_id)
            await self.save_to_memory("documents_index", index_data, context)

    def _get_help_text(self) -> str:
        """Get help text for unknown task types."""
        return """FormatterAgent - Document Generation and Formatting

Supported task types:

1. format_report - Generate complete formatted report
   Input: {
       "plan_data": {...},
       "findings": [{...}, {...}],
       "report_type": "findings_report|executive_summary|...",
       "options": {"title": "Custom Title"}
   }

2. generate_manifest - Generate payload manifest
   Input: {
       "payloads": [{...}, {...}],
       "metadata": {"title": "Manifest Title"}
   }

3. create_document - Create a formatted document
   Input: {
       "document_type": "findings_report",
       "content": {"title": "...", "sections": [...]},
       "output_format": "docx|pdf|markdown|html|json",
       "template": "standard|findings_report"
   }

4. export_evidence - Export evidence bundle
   Input: {
       "plan_id": "plan_id",
       "include_payloads": true,
       "include_findings": true,
       "output_format": "json"
   }

5. format_findings - Format security findings
   Input: {
       "findings": [{...}, {...}],
       "format_style": "standard|detailed|concise"
   }

6. generate_summary - Generate executive summary
   Input: {
       "plan_data": {...},
       "findings": [{...}, {...}]
   }

7. get_document - Retrieve a document
   Input: {"document_id": "document_id"}

8. list_documents - List all documents for session
   Input: {}

A2A Protocol:
- Agent accepts A2A messages on /a2a endpoint
- Supported A2A task types: format_report, generate_manifest, create_document,
  export_evidence, format_findings, generate_summary, health_check
"""


# ============================================================
# FACTORY FUNCTION
# ============================================================

def create_formatter_agent(
    name: str = "formatter",
    model_alias: str = "formatter-agent",
    **config_kwargs,
) -> FormatterAgent:
    """
    Factory function to create a configured FormatterAgent.

    Args:
        name: Agent name
        model_alias: LiteLLM model alias
        **config_kwargs: Additional configuration

    Returns:
        Configured FormatterAgent instance
    """
    # Create agent configuration
    config = AgentConfig(
        name=name,
        role=AgentRole.FORMATTER,
        model_alias=model_alias,
        temperature=0.5,
        enable_long_term_memory=False,  # No long-term memory needed
        **config_kwargs,
    )

    # Formatter doesn't need external tools - generates documents internally
    agent = FormatterAgent(config=config)

    logger.info(f"Created FormatterAgent: {name} with model {model_alias}")
    return agent
