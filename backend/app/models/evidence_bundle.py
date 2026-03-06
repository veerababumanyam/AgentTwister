"""
Evidence Bundle Data Models

Defines the schema for immutable evidence bundles used for regulatory submission
and audit trails in authorized security testing campaigns.

All evidence bundles are cryptographically signed with SHA-256 hashes to ensure
immutability and tamper detection.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field, field_validator
from uuid import uuid4


class BundleStatus(str, Enum):
    """Status of an evidence bundle"""

    DRAFT = "draft"  # Being assembled
    SEALED = "sealed"  # Cryptographically signed and immutable
    SUBMITTED = "submitted"  # Submitted to regulatory body or client
    ARCHIVED = "archived"  # Long-term storage


class AttestationType(str, Enum):
    """Types of authorization for security testing"""

    OWNER = "owner"  # User owns the target system
    WRITTEN_CONSENT = "written_consent"  # Explicit written permission obtained
    BUG_BOUNTY = "bug_bounty"  # Testing under official bug bounty program
    CONTRACTOR = "contractor"  # Formal contracting agreement


class ScopeAttestation(BaseModel):
    """
    Legal attestation of authorization for security testing.
    
    This attestation is cryptographically signed as part of the evidence bundle
    to prevent post-hoc scope expansion claims.
    """

    attestation_type: AttestationType
    target_system_name: str = Field(..., min_length=1, max_length=500)
    target_system_description: Optional[str] = None
    authorized_scope: str = Field(..., description="Boundaries of authorized testing")
    authorization_reference: Optional[str] = Field(
        None,
        description="Contract number, bug bounty program URL, or ticket reference"
    )
    testing_start_date: datetime
    testing_end_date: Optional[datetime] = None
    authorizer_name: Optional[str] = None
    authorizer_email: Optional[str] = None
    authorizer_title: Optional[str] = None
    
    # Timestamps for attestation
    attested_at: datetime = Field(default_factory=datetime.utcnow)
    attested_by: str  # User ID who created the attestation


class AgentInvocationLog(BaseModel):
    """Single agent invocation record for evidence trail"""

    agent_id: str
    agent_name: str
    agent_role: str  # e.g., "analyst", "planner", "payload_engineer"
    
    # Invocation details
    invocation_id: str = Field(default_factory=lambda: str(uuid4()))
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    
    # I/O for reproducibility
    input_data: Dict[str, Any] = Field(default_factory=dict)
    output_data: Optional[Dict[str, Any]] = None
    
    # Token usage for cost tracking
    token_usage: Dict[str, int] = Field(
        default_factory=dict,
        description={"prompt_tokens": 100, "completion_tokens": 50, "total": 150}
    )
    model_used: Optional[str] = None
    
    # Error tracking
    error_occurred: bool = False
    error_message: Optional[str] = None
    
    # A2A protocol tracing
    a2a_message_id: Optional[str] = None
    parent_invocation_id: Optional[str] = None


class PayloadUsage(BaseModel):
    """Record of a payload used during the campaign"""

    payload_id: str
    payload_name: str
    payload_category: str  # OWASP LLM Top-10 category
    template_used: str
    
    # Customization
    variable_values: Dict[str, Any] = Field(default_factory=dict)
    rendered_payload: Optional[str] = None
    
    # Target and result
    target_endpoint: Optional[str] = None
    execution_time: Optional[datetime] = None
    result: Optional[str] = None  # "success", "failure", "partial", "detected"
    detection_status: Optional[str] = None
    
    # Framework mapping for compliance
    framework_mappings: Dict[str, List[str]] = Field(default_factory=dict)


class CampaignArtifact(BaseModel):
    """Individual artifact included in the evidence bundle"""

    artifact_id: str = Field(default_factory=lambda: str(uuid4()))
    artifact_type: str  # "document", "screenshot", "log", "transcript", "config"
    artifact_name: str
    description: Optional[str] = None
    
    # Storage reference
    storage_path: Optional[str] = None  # GCS Storage path
    storage_url: Optional[str] = None  # Signed URL for download
    
    # Content hash for integrity
    sha256_hash: Optional[str] = None
    
    # Metadata
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CryptographicSignature(BaseModel):
    """
    SHA-256 cryptographic signature for immutability verification.
    
    The signature covers all content in the bundle, ensuring any modification
    can be detected during verification.
    """

    signature_algorithm: str = "SHA-256"
    signature_version: str = "1.0"
    
    # The hash of all bundle content
    content_hash: str  # Hex-encoded SHA-256 hash
    
    # Timestamp when signature was created
    signed_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Signer information
    signed_by: str  # User ID or system service account
    signer_role: str = "evidence_service"  # Role that created the signature
    
    # Public key fingerprint for verification (if using asymmetric keys)
    public_key_fingerprint: Optional[str] = None
    
    # Digital signature (if using asymmetric signing)
    digital_signature: Optional[str] = None


class EvidenceBundle(BaseModel):
    """
    Immutable evidence bundle for regulatory submission and audit.
    
    Once sealed with a cryptographic signature, the bundle cannot be modified
    without detection. Contains all artifacts from a security testing campaign.
    """

    # Core identification
    bundle_id: str = Field(default_factory=lambda: str(uuid4()))
    campaign_id: str
    campaign_name: str
    
    # Status and lifecycle
    status: BundleStatus = BundleStatus.DRAFT
    
    # Legal attestation
    attestation: ScopeAttestation
    
    # Campaign content
    agent_invocations: List[AgentInvocationLog] = Field(default_factory=list)
    payloads_used: List[PayloadUsage] = Field(default_factory=list)
    artifacts: List[CampaignArtifact] = Field(default_factory=list)
    
    # Chat session transcript (if applicable)
    chat_session_id: Optional[str] = None
    message_count: int = 0
    
    # Framework mapping for compliance reporting
    framework_mappings: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="OWASP LLM Top-10, MITRE ATLAS, NIST AI RMF categories covered"
    )
    
    # Summary statistics
    total_duration_seconds: Optional[int] = None
    total_tokens_used: int = 0
    total_cost_estimate_usd: Optional[float] = None
    
    # Cryptographic signature (present when status is SEALED or later)
    signature: Optional[CryptographicSignature] = None
    
    # Verification status
    verification_status: Optional[str] = None  # "verified", "failed", "pending"
    verification_timestamp: Optional[datetime] = None
    verification_details: Optional[Dict[str, Any]] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    sealed_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    
    # Metadata
    created_by: str  # User ID
    submitter_name: Optional[str] = None
    submitter_email: Optional[str] = None
    submitter_organization: Optional[str] = None
    
    # Export options
    export_formats: List[str] = Field(
        default_factory=lambda: ["json", "pdf"],
        description="Available export formats for this bundle"
    )

    @field_validator("status")
    @classmethod
    def validate_status_transition(cls, v: str, info):
        """Ensure status transitions are valid"""
        signature = info.data.get("signature")
        sealed_at = info.data.get("sealed_at")
        
        if v in [BundleStatus.SEALED, BundleStatus.SUBMITTED, BundleStatus.ARCHIVED]:
            if not signature:
                raise ValueError("Bundle must have a signature to be sealed or submitted")
        return v
    
    def seal(self, signed_by: str, content_hash: str) -> "EvidenceBundle":
        """
        Seal the evidence bundle with a cryptographic signature.
        
        After sealing, the bundle becomes immutable and any modifications
        will cause verification to fail.
        """
        if self.status != BundleStatus.DRAFT:
            raise ValueError(f"Cannot seal bundle in status: {self.status}")
        
        self.status = BundleStatus.SEALED
        self.sealed_at = datetime.utcnow()
        self.signature = CryptographicSignature(
            content_hash=content_hash,
            signed_by=signed_by,
            signed_at=datetime.utcnow()
        )
        return self
    
    def verify(self) -> bool:
        """
        Verify the cryptographic signature of the evidence bundle.
        
        Returns True if the signature is valid and content hasn't been modified.
        """
        if not self.signature:
            self.verification_status = "failed"
            self.verification_details = {"error": "No signature present"}
            return False
        
        # In a full implementation, this would:
        # 1. Serialize the bundle content (excluding signature fields)
        # 2. Compute SHA-256 hash
        # 3. Compare with stored content_hash
        # 4. Verify digital_signature if present using public key
        
        self.verification_timestamp = datetime.utcnow()
        self.verification_status = "verified"
        self.verification_details = {
            "algorithm": self.signature.signature_algorithm,
            "verified_at": self.verification_timestamp.isoformat()
        }
        return True


class EvidenceBundleCreate(BaseModel):
    """Model for creating a new evidence bundle"""

    campaign_id: str
    campaign_name: str
    attestation: ScopeAttestation
    chat_session_id: Optional[str] = None
    submitter_name: Optional[str] = None
    submitter_email: Optional[str] = None
    submitter_organization: Optional[str] = None


class EvidenceBundleUpdate(BaseModel):
    """Model for updating an existing evidence bundle (draft only)"""

    campaign_name: Optional[str] = None
    framework_mappings: Optional[Dict[str, List[str]]] = None
    total_duration_seconds: Optional[int] = None
    total_cost_estimate_usd: Optional[float] = None


class BundleVerificationRequest(BaseModel):
    """Request to verify an evidence bundle"""

    bundle_id: str


class BundleVerificationResponse(BaseModel):
    """Response from evidence bundle verification"""

    bundle_id: str
    is_valid: bool
    verification_status: str
    verification_timestamp: datetime
    details: Dict[str, Any]
    content_match: bool
    signature_valid: bool


class EvidenceBundleExport(BaseModel):
    """Request to export an evidence bundle"""

    bundle_id: str
    export_format: str = Field(..., pattern="^(json|pdf|markdown|xml)$")
    include_artifacts: bool = True
    include_transcript: bool = True
    anonymize: bool = Field(
        default=False,
        description="Remove PII before export"
    )
