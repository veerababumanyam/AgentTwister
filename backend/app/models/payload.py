"""
Payload Library Data Models

Defines the schema for security testing payload templates stored in SQLite.
These templates are used for authorized red-teaming and security research of LLM applications.

All payloads follow OWASP LLM Top-10 categorization and include framework mappings
for compliance reporting (OWASP ASI, MITRE ATLAS, NIST AI RMF).
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field, field_validator
from uuid import uuid4


class AttackCategory(str, Enum):
    """OWASP LLM Top-10 Attack Categories"""

    LLM01_PROMPT_INJECTION = "LLM01: Prompt Injection"
    LLM02_INSECURE_OUTPUT = "LLM02: Insecure Output Handling"
    LLM03_DATA_POISONING = "LLM03: Training Data Poisoning"
    LLM04_MODEL_DOS = "LLM04: Model Denial of Service"
    LLM05_SUPPLY_CHAIN = "LLM05: Supply Chain Vulnerabilities"
    LLM06_SENSITIVE_INFO = "LLM06: Sensitive Information Disclosure"
    LLM07_INSECURE_PLUGIN = "LLM07: Insecure Plugin Design"
    LLM08_AUTHORIZATION = "LLM08: Authorization Bypass"
    LLM09_OVERRELIANCE = "LLM09: Overreliance on Model"
    LLM10_MODEL_THEFT = "LLM10: Model Theft"


class FrameworkMapping(str, Enum):
    """Compliance Framework Mappings"""

    OWASP_ASI = "OWASP AI Security Standard"
    MITRE_ATLAS = "MITRE Adversarial Threat Landscape for AI Systems"
    NIST_AI_RMF = "NIST AI Risk Management Framework"
    ISO_42001 = "ISO/IEC 42001 AI Management System"
    EU_AI_ACT = "EU AI Act"


class ComplexityLevel(str, Enum):
    """Payload Complexity Classification"""

    BASIC = "basic"  # Simple, direct attacks
    INTERMEDIATE = "intermediate"  # Requires some context or multi-step
    ADVANCED = "advanced"  # Complex, multi-stage, context-aware
    EXPERT = "expert"  # Sophisticated, requires deep understanding


class EffectivenessMetrics(BaseModel):
    """Historical effectiveness data for a payload template"""

    success_rate: float = Field(ge=0, le=1, description="Historical success rate (0-1)")
    total_attempts: int = Field(ge=0, description="Number of times this payload was used")
    last_used: Optional[datetime] = None
    avg_detection_time_ms: Optional[int] = None
    framework_success_rates: Dict[str, float] = Field(
        default_factory=dict,
        description="Success rates broken down by target framework"
    )


class PayloadTemplate(BaseModel):
    """
    Core payload template model for security testing.

    This model represents a reusable security testing payload template
    that can be customized for specific target systems.
    """

    # Core identification
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=1, max_length=200)

    # Classification
    category: AttackCategory
    subcategory: Optional[str] = Field(None, max_length=100)
    complexity: ComplexityLevel = ComplexityLevel.BASIC

    # Payload content
    template: str = Field(..., description="The payload template with {{placeholders}}")
    description: str = Field(..., min_length=1, max_length=1000)
    variables: List[str] = Field(
        default_factory=list,
        description="List of placeholder variables in the template"
    )

    # Framework mappings for compliance
    framework_mappings: Dict[FrameworkMapping, List[str]] = Field(
        default_factory=dict,
        description="Mappings to compliance framework categories"
    )

    # Target applicability
    target_frameworks: List[str] = Field(
        default_factory=list,
        description="LLM frameworks this payload applies to (e.g., LangChain, AutoGPT)"
    )
    target_models: List[str] = Field(
        default_factory=list,
        description="Model families this targets (e.g., GPT-4, Claude, Llama)"
    )

    # Effectiveness and feedback
    effectiveness_metrics: Optional[EffectivenessMetrics] = None
    user_rating: float = Field(default=0.0, ge=0, le=5)
    user_feedback_count: int = Field(default=0, ge=0)

    # Metadata
    tags: List[str] = Field(default_factory=list)
    author: Optional[str] = None
    source: Optional[str] = Field(
        None,
        description="Source of this payload (e.g., 'ARTEMIS', 'Community', 'Internal')"
    )
    references: List[str] = Field(
        default_factory=list,
        description="URLs to research papers, writeups, or CVE entries"
    )

    # Versioning and status
    version: str = "1.0.0"
    is_active: bool = True
    is_deprecated: bool = False
    deprecation_reason: Optional[str] = None

    # Safety and authorization
    requires_secondary_confirmation: bool = Field(
        default=False,
        description="Destructive payloads require secondary confirmation"
    )
    risk_level: str = Field(
        default="low",
        pattern="^(low|medium|high|critical)$",
        description="Potential risk level if used improperly"
    )

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        """Ensure slug is URL-safe."""
        if not v or not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Slug must contain only alphanumeric characters, hyphens, and underscores")
        return v.lower().replace(" ", "-")

    @field_validator("template")
    @classmethod
    def validate_template_has_variables(cls, v: str, info) -> str:
        """Ensure template variables match the declared variables list."""
        import re

        # Extract {{variable}} patterns from template
        pattern = r"\{\{(\w+)\}\}"
        found_vars = set(re.findall(pattern, v))

        # Get declared variables from validation context
        declared_vars = set(info.data.get("variables", []))

        # Warn if there's a mismatch (but don't fail - allow for optional vars)
        if found_vars != declared_vars:
            # Auto-populate variables if empty
            if not declared_vars and found_vars:
                info.data["variables"] = list(found_vars)

        return v


class PayloadTemplateCreate(BaseModel):
    """Model for creating new payload templates (without auto-generated fields)"""

    name: str = Field(..., min_length=1, max_length=200)
    slug: Optional[str] = None
    category: AttackCategory
    subcategory: Optional[str] = None
    complexity: ComplexityLevel = ComplexityLevel.BASIC
    template: str
    description: str
    variables: List[str] = Field(default_factory=list)
    framework_mappings: Dict[FrameworkMapping, List[str]] = Field(default_factory=dict)
    target_frameworks: List[str] = Field(default_factory=list)
    target_models: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    author: Optional[str] = None
    source: Optional[str] = None
    references: List[str] = Field(default_factory=list)
    requires_secondary_confirmation: bool = False
    risk_level: str = "low"


class PayloadTemplateUpdate(BaseModel):
    """Model for updating existing payload templates"""

    name: Optional[str] = None
    slug: Optional[str] = None
    category: Optional[AttackCategory] = None
    subcategory: Optional[str] = None
    complexity: Optional[ComplexityLevel] = None
    template: Optional[str] = None
    description: Optional[str] = None
    variables: Optional[List[str]] = None
    framework_mappings: Optional[Dict[FrameworkMapping, List[str]]] = None
    target_frameworks: Optional[List[str]] = None
    target_models: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None
    is_deprecated: Optional[bool] = None
    deprecation_reason: Optional[str] = None
    version: Optional[str] = None
    requires_secondary_confirmation: Optional[bool] = None
    risk_level: Optional[str] = None


class PayloadSearchFilters(BaseModel):
    """Filters for searching payload templates"""

    category: Optional[AttackCategory] = None
    subcategory: Optional[str] = None
    complexity: Optional[ComplexityLevel] = None
    target_framework: Optional[str] = None
    target_model: Optional[str] = None
    tags: Optional[List[str]] = None
    risk_level: Optional[str] = None
    is_active: bool = True
    min_effectiveness: Optional[float] = Field(
        None,
        ge=0,
        le=1,
        description="Minimum success rate filter"
    )
    framework_mapping: Optional[FrameworkMapping] = None


class PayloadRenderRequest(BaseModel):
    """Request to render a payload template with specific values"""

    template_id: str
    variable_values: Dict[str, Any] = Field(default_factory=dict)
    context: Optional[str] = Field(
        None,
        description="Additional context to include when rendering"
    )


class PayloadRenderResponse(BaseModel):
    """Response containing a rendered payload"""

    rendered_payload: str
    template_id: str
    template_name: str
    warnings: List[str] = Field(
        default_factory=list,
        description="Warnings about missing variables or potential issues"
    )
    requires_confirmation: bool = Field(
        default=False,
        description="Whether this payload requires secondary confirmation before use"
    )


# ============================================================
# DOCUMENT GENERATION MODELS
# ============================================================

class StealthTechnique(str, Enum):
    """Techniques for embedding payloads invisibly in documents."""

    FONT_COLOR_MATCH = "font_color_match"  # Text color matches background
    ZERO_WIDTH_UNICODE = "zero_width_unicode"  # Zero-width characters
    WHITE_ON_WHITE = "white_on_white"  # White text on white background
    TINY_FONT = "tiny_font"  # Font size 1pt
    HIDDEN_TEXT_PROPERTY = "hidden_text_property"  # Using hidden formatting
    METADATA_INJECTION = "metadata_injection"  # Embedded in document metadata
    FOOTNOTE_EMBEDDING = "footnote_embedding"  # Hidden in footnotes
    COMMENT_INJECTION = "comment_injection"  # Hidden in document comments
    HEADER_FOOTER_HIDDEN = "header_footer_hidden"  # Hidden in headers/footers
    INVISIBLE_TABLE = "invisible_table"  # Table with invisible borders
    OVERLAY_TEXT = "overlay_text"  # Text overlaid on matching text


class DocumentTemplate(str, Enum):
    """Predefined document templates."""

    BUSINESS_MEMO = "business_memo"
    TECHNICAL_REPORT = "technical_report"
    FINANCIAL_STATEMENT = "financial_statement"
    INTERNAL_POLICY = "internal_policy"
    PROJECT_PROPOSAL = "project_proposal"
    MEETING_MINUTES = "meeting_minutes"
    EMAIL_ATTACHMENT = "email_attachment"
    RESUME = "resume"
    ACADEMIC_PAPER = "academic_paper"
    INVOICE = "invoice"
    CUSTOM = "custom"


class PayloadEmbedding(BaseModel):
    """Configuration for embedding a payload in a document."""

    payload: str = Field(..., description="The payload text to embed")
    technique: StealthTechnique = Field(
        default=StealthTechnique.FONT_COLOR_MATCH,
        description="The stealth technique to use"
    )
    position: str = Field(
        default="end",
        description="Where to embed: 'start', 'end', 'after_text', 'before_text'"
    )
    anchor_text: Optional[str] = Field(
        None,
        description="Anchor text if position is 'after_text' or 'before_text'"
    )
    additional_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional configuration for the technique"
    )


class DocumentGenerationRequest(BaseModel):
    """Request for generating an adversarial DOCX document."""

    template: DocumentTemplate = Field(
        default=DocumentTemplate.BUSINESS_MEMO,
        description="Document template to use"
    )
    visible_content: str = Field(
        ...,
        min_length=10,
        description="The visible content that appears in the document"
    )
    payload_embeddings: List[PayloadEmbedding] = Field(
        default_factory=list,
        description="Payloads to embed using stealth techniques"
    )
    metadata: Optional[Dict[str, str]] = Field(
        None,
        description="Custom document metadata (author, title, etc.)"
    )
    filename: Optional[str] = Field(
        None,
        description="Output filename (without extension)"
    )


class DocumentGenerationResponse(BaseModel):
    """Response from document generation."""

    document_id: str = Field(default_factory=lambda: str(uuid4()))
    filename: str
    file_size_bytes: int
    mime_type: str = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    download_url: Optional[str] = None
    embedded_payloads: List[str] = Field(default_factory=list)
    stealth_techniques_used: List[StealthTechnique] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================
# PDF GENERATION MODELS
# ============================================================

class PDFStealthTechnique(str, Enum):
    """PDF-specific stealth techniques for embedding payloads."""

    # Universal techniques (also work in DOCX)
    FONT_COLOR_MATCH = "font_color_match"
    ZERO_WIDTH_UNICODE = "zero_width_unicode"
    WHITE_ON_WHITE = "white_on_white"
    TINY_FONT = "tiny_font"
    METADATA_INJECTION = "metadata_injection"

    # PDF-specific techniques
    HIDDEN_LAYER = "hidden_layer"  # PDF Optional Content Groups
    ANNOTATION_HIDDEN = "annotation_hidden"  # Hidden PDF annotations
    INVISIBLE_FORM_FIELD = "invisible_form_field"  # Hidden form fields


class PDFPayloadEmbedding(BaseModel):
    """Configuration for embedding a payload in a PDF document."""

    payload: str = Field(..., description="The payload text to embed")
    technique: PDFStealthTechnique = Field(
        default=PDFStealthTechnique.FONT_COLOR_MATCH,
        description="The stealth technique to use"
    )
    position: str = Field(
        default="end",
        description="Where to embed: 'start', 'end', 'after_text', 'before_text'"
    )
    anchor_text: Optional[str] = Field(
        None,
        description="Anchor text if position is 'after_text' or 'before_text'"
    )
    additional_config: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional configuration for the technique"
    )


class PDFGenerationRequest(BaseModel):
    """Request for generating an adversarial PDF document."""

    template: DocumentTemplate = Field(
        default=DocumentTemplate.BUSINESS_MEMO,
        description="Document template to use"
    )
    visible_content: str = Field(
        ...,
        min_length=10,
        description="The visible content that appears in the document"
    )
    payload_embeddings: List[PDFPayloadEmbedding] = Field(
        default_factory=list,
        description="Payloads to embed using stealth techniques"
    )
    metadata: Optional[Dict[str, str]] = Field(
        None,
        description="Custom PDF metadata (author, title, subject, etc.)"
    )
    filename: Optional[str] = Field(
        None,
        description="Output filename (without extension)"
    )
    generate_dual_view: bool = Field(
        default=False,
        description="Generate dual-view preview (human-visible vs LLM-parsed)"
    )


class DualViewPreview(BaseModel):
    """Dual-view preview showing human-visible vs LLM-parsed content."""

    human_visible_preview: str = Field(
        ...,
        description="What humans see when viewing the document"
    )
    llm_parsed_preview: str = Field(
        ...,
        description="What an LLM extracts when parsing the document"
    )
    extracted_payloads: List[str] = Field(
        default_factory=list,
        description="Payloads extracted from the document"
    )


class PDFGenerationResponse(BaseModel):
    """Response from PDF document generation."""

    document_id: str = Field(default_factory=lambda: str(uuid4()))
    filename: str
    file_size_bytes: int
    mime_type: str = "application/pdf"
    download_url: Optional[str] = None
    content_base64: Optional[str] = None
    embedded_payloads_count: int = 0
    stealth_techniques_used: List[str] = Field(default_factory=list)
    dual_view: Optional[DualViewPreview] = None
    warnings: List[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
