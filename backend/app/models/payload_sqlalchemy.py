"""
SQLAlchemy Models for Payload Library

Defines the database schema for payload templates using SQLAlchemy ORM.
"""

from datetime import datetime
from typing import Optional, List
import json

from sqlalchemy import (
    String, Text, Boolean, Float, Integer, DateTime, JSON, Enum as SQLEnum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.payload import AttackCategory, ComplexityLevel, FrameworkMapping


class PayloadTemplateDB(Base):
    """SQLAlchemy model for payload templates"""
    __tablename__ = "payload_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    subcategory: Mapped[Optional[str]] = mapped_column(String(100))
    complexity: Mapped[str] = mapped_column(String(20), default="basic")
    template: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[Optional[str]] = mapped_column(JSON, default=list)
    target_frameworks: Mapped[Optional[str]] = mapped_column(JSON, default=list)
    target_models: Mapped[Optional[str]] = mapped_column(JSON, default=list)
    framework_mappings: Mapped[Optional[str]] = mapped_column(JSON, default=dict)
    effectiveness_metrics: Mapped[Optional[str]] = mapped_column(JSON, default=dict)
    user_rating: Mapped[float] = mapped_column(Float, default=0.0)
    user_feedback_count: Mapped[int] = mapped_column(Integer, default=0)
    tags: Mapped[Optional[str]] = mapped_column(JSON, default=list)
    author: Mapped[Optional[str]] = mapped_column(String(255))
    source: Mapped[Optional[str]] = mapped_column(String(255))
    references: Mapped[Optional[str]] = mapped_column(JSON, default=list)
    version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_deprecated: Mapped[bool] = mapped_column(Boolean, default=False)
    deprecation_reason: Mapped[Optional[str]] = mapped_column(Text)
    requires_secondary_confirmation: Mapped[bool] = mapped_column(Boolean, default=False)
    risk_level: Mapped[str] = mapped_column(String(20), default="low")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<PayloadTemplateDB(id={self.id}, name={self.name}, category={self.category})>"
