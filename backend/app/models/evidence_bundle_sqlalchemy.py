"""
SQLAlchemy Models for Evidence Bundles

Defines the database schema for evidence bundles using SQLAlchemy ORM.
"""

from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import (
    String, Text, Boolean, Float, Integer, DateTime, JSON, ForeignKey
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EvidenceBundleDB(Base):
    """SQLAlchemy model for evidence bundles"""
    __tablename__ = "evidence_bundles"

    bundle_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    campaign_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    attestation: Mapped[Optional[str]] = mapped_column(JSON, default=dict)
    chat_session_id: Mapped[Optional[str]] = mapped_column(String(255))
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    framework_mappings: Mapped[Optional[str]] = mapped_column(JSON, default=dict)
    total_duration_seconds: Mapped[Optional[float]] = mapped_column(Float)
    total_tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    total_cost_estimate_usd: Mapped[Optional[float]] = mapped_column(Float)
    signature: Mapped[Optional[str]] = mapped_column(JSON)
    verification_status: Mapped[Optional[str]] = mapped_column(String(20))
    verification_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime)
    verification_details: Mapped[Optional[str]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    sealed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    submitter_name: Mapped[Optional[str]] = mapped_column(String(255))
    submitter_email: Mapped[Optional[str]] = mapped_column(String(255))
    submitter_organization: Mapped[Optional[str]] = mapped_column(String(255))
    export_formats: Mapped[Optional[str]] = mapped_column(JSON, default=list)

    # Relationships
    agent_invocations: Mapped[list["AgentInvocationDB"]] = relationship(
        back_populates="bundle", cascade="all, delete-orphan"
    )
    payloads_used: Mapped[list["PayloadUsageDB"]] = relationship(
        back_populates="bundle", cascade="all, delete-orphan"
    )
    artifacts: Mapped[list["CampaignArtifactDB"]] = relationship(
        back_populates="bundle", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<EvidenceBundleDB(bundle_id={self.bundle_id}, campaign={self.campaign_name})>"


class AgentInvocationDB(Base):
    """SQLAlchemy model for agent invocation logs"""
    __tablename__ = "agent_invocations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bundle_id: Mapped[str] = mapped_column(String(36), ForeignKey("evidence_bundles.bundle_id"), nullable=False)
    agent_id: Mapped[str] = mapped_column(String(255), nullable=False)
    agent_name: Mapped[str] = mapped_column(String(255), nullable=False)
    agent_role: Mapped[str] = mapped_column(String(255), nullable=False)
    invocation_id: Mapped[str] = mapped_column(String(36), default=lambda: str(uuid.uuid4()))
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)
    input_data: Mapped[Optional[str]] = mapped_column(JSON, default=dict)
    output_data: Mapped[Optional[str]] = mapped_column(JSON)
    token_usage: Mapped[Optional[str]] = mapped_column(JSON, default=dict)
    model_used: Mapped[Optional[str]] = mapped_column(String(255))
    error_occurred: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    a2a_message_id: Mapped[Optional[str]] = mapped_column(String(255))
    parent_invocation_id: Mapped[Optional[str]] = mapped_column(String(36))

    bundle: Mapped["EvidenceBundleDB"] = relationship(back_populates="agent_invocations")


class PayloadUsageDB(Base):
    """SQLAlchemy model for payload usage records"""
    __tablename__ = "payload_usages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bundle_id: Mapped[str] = mapped_column(String(36), ForeignKey("evidence_bundles.bundle_id"), nullable=False)
    payload_id: Mapped[str] = mapped_column(String(36), nullable=False)
    payload_name: Mapped[str] = mapped_column(String(255), nullable=False)
    payload_category: Mapped[str] = mapped_column(String(50), nullable=False)
    template_used: Mapped[str] = mapped_column(Text, nullable=False)
    variable_values: Mapped[Optional[str]] = mapped_column(JSON, default=dict)
    rendered_payload: Mapped[Optional[str]] = mapped_column(Text)
    target_endpoint: Mapped[Optional[str]] = mapped_column(String(500))
    execution_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    result: Mapped[Optional[str]] = mapped_column(Text)
    detection_status: Mapped[Optional[str]] = mapped_column(String(50))
    framework_mappings: Mapped[Optional[str]] = mapped_column(JSON, default=dict)

    bundle: Mapped["EvidenceBundleDB"] = relationship(back_populates="payloads_used")


class CampaignArtifactDB(Base):
    """SQLAlchemy model for campaign artifacts"""
    __tablename__ = "campaign_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bundle_id: Mapped[str] = mapped_column(String(36), ForeignKey("evidence_bundles.bundle_id"), nullable=False)
    artifact_id: Mapped[str] = mapped_column(String(36), default=lambda: str(uuid.uuid4()))
    artifact_type: Mapped[str] = mapped_column(String(50), nullable=False)
    artifact_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    storage_path: Mapped[Optional[str]] = mapped_column(String(500))
    storage_url: Mapped[Optional[str]] = mapped_column(String(500))
    sha256_hash: Mapped[Optional[str]] = mapped_column(String(64))
    mime_type: Mapped[Optional[str]] = mapped_column(String(100))
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    bundle: Mapped["EvidenceBundleDB"] = relationship(back_populates="artifacts")
