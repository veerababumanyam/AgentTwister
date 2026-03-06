"""
Payload Library Service

Provides CRUD operations and search functionality for the payload library
stored in SQLite. This is the core service for managing security testing
payload templates.
"""

import logging
import re
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, stop_after_attempt, wait_exponential

from app.database import async_session_maker
from app.models.payload import (
    PayloadTemplate,
    PayloadTemplateCreate,
    PayloadTemplateUpdate,
    PayloadSearchFilters,
    AttackCategory,
    ComplexityLevel,
    FrameworkMapping,
    EffectivenessMetrics,
)
from app.models.payload_sqlalchemy import PayloadTemplateDB

logger = logging.getLogger(__name__)


class PayloadLibraryService:
    """
    Service for managing the payload library in SQLite.

    Provides methods for creating, reading, updating, deleting, and searching
    payload templates. All operations are logged and include error handling.
    """

    def __init__(self, session: Optional[AsyncSession] = None):
        self._session = session
        # Lazy load framework mapping service to avoid circular imports
        self._mapping_service = None

    @property
    def mapping_service(self):
        """Lazy load the framework mapping service"""
        if self._mapping_service is None:
            from app.services.framework_mapping import get_framework_mapping_service
            self._mapping_service = get_framework_mapping_service()
        return self._mapping_service

    async def _get_session(self) -> AsyncSession:
        """Get database session"""
        if self._session:
            return self._session
        return async_session_maker()

    def _db_to_pydantic(self, db_obj: PayloadTemplateDB) -> PayloadTemplate:
        """Convert database model to Pydantic model"""
        return PayloadTemplate(
            id=db_obj.id,
            name=db_obj.name,
            slug=db_obj.slug,
            category=AttackCategory(db_obj.category),
            subcategory=db_obj.subcategory,
            complexity=ComplexityLevel(db_obj.complexity),
            template=db_obj.template,
            description=db_obj.description,
            variables=db_obj.variables or [],
            framework_mappings=self._parse_framework_mappings(db_obj.framework_mappings),
            target_frameworks=db_obj.target_frameworks or [],
            target_models=db_obj.target_models or [],
            effectiveness_metrics=self._parse_effectiveness_metrics(db_obj.effectiveness_metrics),
            user_rating=db_obj.user_rating,
            user_feedback_count=db_obj.user_feedback_count,
            tags=db_obj.tags or [],
            author=db_obj.author,
            source=db_obj.source,
            references=db_obj.references or [],
            version=db_obj.version,
            is_active=db_obj.is_active,
            is_deprecated=db_obj.is_deprecated,
            deprecation_reason=db_obj.deprecation_reason,
            requires_secondary_confirmation=db_obj.requires_secondary_confirmation,
            risk_level=db_obj.risk_level,
            created_at=db_obj.created_at,
            updated_at=db_obj.updated_at,
        )

    def _parse_framework_mappings(self, data: Optional[Dict]) -> Dict[FrameworkMapping, List[str]]:
        """Parse framework mappings from JSON"""
        if not data:
            return {}
        result = {}
        for key, value in data.items():
            try:
                enum_key = FrameworkMapping(key)
                result[enum_key] = value
            except ValueError:
                continue
        return result

    def _parse_effectiveness_metrics(self, data: Optional[Dict]) -> Optional[EffectivenessMetrics]:
        """Parse effectiveness metrics from JSON"""
        if not data:
            return None
        return EffectivenessMetrics(
            success_rate=data.get("success_rate", 0.0),
            total_attempts=data.get("total_attempts", 0),
            last_used=datetime.fromisoformat(data["last_used"]) if data.get("last_used") else None,
            avg_detection_time_ms=data.get("avg_detection_time_ms"),
            framework_success_rates=data.get("framework_success_rates", {}),
        )

    def _pydantic_to_db(self, payload: PayloadTemplate) -> PayloadTemplateDB:
        """Convert Pydantic model to database model"""
        return PayloadTemplateDB(
            id=payload.id,
            name=payload.name,
            slug=payload.slug,
            category=payload.category.value,
            subcategory=payload.subcategory,
            complexity=payload.complexity.value,
            template=payload.template,
            description=payload.description,
            variables=payload.variables,
            target_frameworks=payload.target_frameworks,
            target_models=payload.target_models,
            framework_mappings={k.value: v for k, v in payload.framework_mappings.items()},
            effectiveness_metrics={
                "success_rate": payload.effectiveness_metrics.success_rate if payload.effectiveness_metrics else 0,
                "total_attempts": payload.effectiveness_metrics.total_attempts if payload.effectiveness_metrics else 0,
                "last_used": payload.effectiveness_metrics.last_used.isoformat() if payload.effectiveness_metrics and payload.effectiveness_metrics.last_used else None,
                "avg_detection_time_ms": payload.effectiveness_metrics.avg_detection_time_ms if payload.effectiveness_metrics else None,
                "framework_success_rates": payload.effectiveness_metrics.framework_success_rates if payload.effectiveness_metrics else {},
            } if payload.effectiveness_metrics else None,
            user_rating=payload.user_rating,
            user_feedback_count=payload.user_feedback_count,
            tags=payload.tags,
            author=payload.author,
            source=payload.source,
            references=payload.references,
            version=payload.version,
            is_active=payload.is_active,
            is_deprecated=payload.is_deprecated,
            deprecation_reason=payload.deprecation_reason,
            requires_secondary_confirmation=payload.requires_secondary_confirmation,
            risk_level=payload.risk_level,
            created_at=payload.created_at,
            updated_at=payload.updated_at,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def create_payload(
        self, payload_create: PayloadTemplateCreate, author: Optional[str] = None
    ) -> PayloadTemplate:
        """
        Create a new payload template in the library.

        Args:
            payload_create: The payload template data to create
            author: Optional author identifier

        Returns:
            The created PayloadTemplate

        Raises:
            ValueError: If slug already exists
        """
        async with await self._get_session() as session:
            # Check for existing slug
            existing = await self.get_by_slug(payload_create.slug or "")
            if existing:
                raise ValueError(f"Payload with slug '{payload_create.slug}' already exists")

            # Determine framework mappings
            framework_mappings = payload_create.framework_mappings
            if not framework_mappings:
                # Auto-generate framework mappings based on payload characteristics
                framework_mappings = self.mapping_service.infer_mappings(
                    category=payload_create.category,
                    template=payload_create.template,
                    description=payload_create.description,
                    tags=payload_create.tags,
                    subcategory=payload_create.subcategory,
                    complexity=payload_create.complexity.value if payload_create.complexity else None,
                    risk_level=payload_create.risk_level,
                )
                logger.info(f"Auto-generated framework mappings for payload: {list(framework_mappings.keys())}")

            # Create the payload template
            payload = PayloadTemplate(
                name=payload_create.name,
                slug=payload_create.slug or self._slugify(payload_create.name),
                category=payload_create.category,
                subcategory=payload_create.subcategory,
                complexity=payload_create.complexity,
                template=payload_create.template,
                description=payload_create.description,
                variables=payload_create.variables,
                framework_mappings=framework_mappings,
                target_frameworks=payload_create.target_frameworks,
                target_models=payload_create.target_models,
                tags=payload_create.tags,
                author=author or payload_create.author,
                source=payload_create.source,
                references=payload_create.references,
                requires_secondary_confirmation=payload_create.requires_secondary_confirmation,
                risk_level=payload_create.risk_level,
            )

            db_obj = self._pydantic_to_db(payload)
            session.add(db_obj)
            await session.commit()

            logger.info(f"Created payload template: {payload.id} - {payload.name}")
            return payload

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def get_by_id(self, payload_id: str) -> Optional[PayloadTemplate]:
        """Retrieve a payload template by ID."""
        async with await self._get_session() as session:
            result = await session.execute(
                select(PayloadTemplateDB).where(PayloadTemplateDB.id == payload_id)
            )
            db_obj = result.scalar_one_or_none()
            if not db_obj:
                return None
            return self._db_to_pydantic(db_obj)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def get_by_slug(self, slug: str) -> Optional[PayloadTemplate]:
        """Retrieve a payload template by slug."""
        async with await self._get_session() as session:
            result = await session.execute(
                select(PayloadTemplateDB).where(PayloadTemplateDB.slug == slug)
            )
            db_obj = result.scalar_one_or_none()
            if not db_obj:
                return None
            return self._db_to_pydantic(db_obj)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def list_all(
        self,
        limit: int = 100,
        offset: int = 0,
        active_only: bool = True,
    ) -> List[PayloadTemplate]:
        """List all payload templates with pagination."""
        async with await self._get_session() as session:
            query = select(PayloadTemplateDB)

            if active_only:
                query = query.where(
                    and_(
                        PayloadTemplateDB.is_active == True,
                        PayloadTemplateDB.is_deprecated == False
                    )
                )

            query = query.order_by(PayloadTemplateDB.name)
            query = query.offset(offset).limit(limit)

            result = await session.execute(query)
            db_objs = result.scalars().all()
            return [self._db_to_pydantic(obj) for obj in db_objs]

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def search(self, filters: PayloadSearchFilters, limit: int = 50) -> List[PayloadTemplate]:
        """Search payload templates using the provided filters."""
        async with await self._get_session() as session:
            query = select(PayloadTemplateDB)

            # Apply filters
            conditions = []

            if filters.category:
                conditions.append(PayloadTemplateDB.category == filters.category.value)

            if filters.subcategory:
                conditions.append(PayloadTemplateDB.subcategory == filters.subcategory)

            if filters.complexity:
                conditions.append(PayloadTemplateDB.complexity == filters.complexity.value)

            if filters.risk_level:
                conditions.append(PayloadTemplateDB.risk_level == filters.risk_level)

            if filters.is_active is not None:
                conditions.append(PayloadTemplateDB.is_active == filters.is_active)

            if conditions:
                query = query.where(and_(*conditions))

            query = query.limit(limit)

            result = await session.execute(query)
            db_objs = result.scalars().all()

            payloads = [self._db_to_pydantic(obj) for obj in db_objs]

            # Post-filter for tags (JSON field)
            if filters.tags:
                payloads = [p for p in payloads if any(tag in p.tags for tag in filters.tags)]

            # Post-filter for effectiveness
            if filters.min_effectiveness:
                payloads = [
                    p for p in payloads
                    if p.effectiveness_metrics and p.effectiveness_metrics.success_rate >= filters.min_effectiveness
                ]

            # Post-filter for framework mapping
            if filters.framework_mapping:
                payloads = [
                    p for p in payloads
                    if filters.framework_mapping.value in [fm.value for fm in p.framework_mappings.keys()]
                ]

            return payloads

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def full_text_search(self, query: str, limit: int = 20) -> List[PayloadTemplate]:
        """
        Full-text search across payload name, description, and template.
        """
        async with await self._get_session() as session:
            search_term = f"%{query.lower()}%"
            db_query = select(PayloadTemplateDB).where(
                and_(
                    PayloadTemplateDB.is_active == True,
                    or_(
                        PayloadTemplateDB.name.ilike(search_term),
                        PayloadTemplateDB.description.ilike(search_term),
                        PayloadTemplateDB.template.ilike(search_term),
                    )
                )
            ).limit(limit)

            result = await session.execute(db_query)
            db_objs = result.scalars().all()
            return [self._db_to_pydantic(obj) for obj in db_objs]

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def update_payload(
        self,
        payload_id: str,
        payload_update: PayloadTemplateUpdate,
    ) -> Optional[PayloadTemplate]:
        """Update an existing payload template."""
        async with await self._get_session() as session:
            result = await session.execute(
                select(PayloadTemplateDB).where(PayloadTemplateDB.id == payload_id)
            )
            db_obj = result.scalar_one_or_none()

            if not db_obj:
                return None

            # Update fields
            update_data = payload_update.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                if hasattr(db_obj, field):
                    setattr(db_obj, field, value)

            db_obj.updated_at = datetime.utcnow()
            await session.commit()

            return self._db_to_pydantic(db_obj)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def delete_payload(self, payload_id: str, hard_delete: bool = False) -> bool:
        """Delete a payload template."""
        async with await self._get_session() as session:
            result = await session.execute(
                select(PayloadTemplateDB).where(PayloadTemplateDB.id == payload_id)
            )
            db_obj = result.scalar_one_or_none()

            if not db_obj:
                return False

            if hard_delete:
                await session.delete(db_obj)
                logger.info(f"Hard deleted payload template: {payload_id}")
            else:
                db_obj.is_active = False
                db_obj.is_deprecated = True
                db_obj.deprecation_reason = "Deleted by user"
                db_obj.updated_at = datetime.utcnow()
                logger.info(f"Soft deleted payload template: {payload_id}")

            await session.commit()
            return True

    async def record_usage(
        self,
        payload_id: str,
        success: bool,
        target_framework: Optional[str] = None,
        detection_time_ms: Optional[int] = None,
    ) -> None:
        """Record usage of a payload template for effectiveness tracking."""
        async with await self._get_session() as session:
            result = await session.execute(
                select(PayloadTemplateDB).where(PayloadTemplateDB.id == payload_id)
            )
            db_obj = result.scalar_one_or_none()

            if not db_obj:
                return

            metrics = db_obj.effectiveness_metrics or {}

            new_total = metrics.get("total_attempts", 0) + 1
            current_successes = metrics.get("success_rate", 0) * metrics.get("total_attempts", 0)
            if success:
                current_successes += 1

            metrics["total_attempts"] = new_total
            metrics["success_rate"] = current_successes / new_total if new_total > 0 else 0
            metrics["last_used"] = datetime.utcnow().isoformat()

            if detection_time_ms is not None:
                current_avg = metrics.get("avg_detection_time_ms")
                if current_avg is None:
                    metrics["avg_detection_time_ms"] = detection_time_ms
                else:
                    metrics["avg_detection_time_ms"] = current_avg * 0.9 + detection_time_ms * 0.1

            if target_framework and success:
                framework_rates = metrics.get("framework_success_rates", {})
                current_rate = framework_rates.get(target_framework, 0.5)
                framework_rates[target_framework] = current_rate * 0.8 + 1.0 * 0.2
                metrics["framework_success_rates"] = framework_rates

            db_obj.effectiveness_metrics = metrics
            await session.commit()

            logger.debug(f"Recorded usage for payload {payload_id}: success={success}")

    async def add_feedback(
        self,
        payload_id: str,
        rating: float,
        user_id: Optional[str] = None,
    ) -> Optional[PayloadTemplate]:
        """Add user feedback rating to a payload template."""
        async with await self._get_session() as session:
            result = await session.execute(
                select(PayloadTemplateDB).where(PayloadTemplateDB.id == payload_id)
            )
            db_obj = result.scalar_one_or_none()

            if not db_obj:
                return None

            current_total = db_obj.user_rating * db_obj.user_feedback_count
            new_count = db_obj.user_feedback_count + 1
            db_obj.user_rating = (current_total + rating) / new_count
            db_obj.user_feedback_count = new_count

            await session.commit()

            logger.info(f"Added feedback for payload {payload_id}: rating={rating}")
            return self._db_to_pydantic(db_obj)

    async def get_by_category(self, category: AttackCategory) -> List[PayloadTemplate]:
        """Get all payloads in a specific OWASP LLM Top-10 category."""
        filters = PayloadSearchFilters(category=category, is_active=True)
        return await self.search(filters, limit=200)

    async def get_categories(self) -> Dict[str, int]:
        """Get count of payloads by category."""
        all_payloads = await self.list_all(active_only=True, limit=1000)
        counts = {}
        for payload in all_payloads:
            category = payload.category.value
            counts[category] = counts.get(category, 0) + 1
        return counts

    async def bulk_import(self, payloads: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Bulk import payload templates into SQLite."""
        imported = 0
        failed = 0
        errors = []

        async with await self._get_session() as session:
            for payload_data in payloads:
                try:
                    # Validate required fields
                    if not payload_data.get("name") or not payload_data.get("template"):
                        failed += 1
                        errors.append(f"Missing required fields: {payload_data.get('id', 'unknown')}")
                        continue

                    payload_id = payload_data.get("id", str(__import__('uuid').uuid4()))
                    slug = payload_data.get("slug") or self._slugify(payload_data["name"])

                    db_obj = PayloadTemplateDB(
                        id=payload_id,
                        name=payload_data["name"],
                        slug=slug,
                        category=payload_data.get("category", "prompt_injection"),
                        subcategory=payload_data.get("subcategory"),
                        complexity=payload_data.get("complexity", "basic"),
                        template=payload_data["template"],
                        description=payload_data.get("description", ""),
                        variables=payload_data.get("variables", []),
                        target_frameworks=payload_data.get("target_frameworks", []),
                        target_models=payload_data.get("target_models", []),
                        framework_mappings=payload_data.get("framework_mappings", {}),
                        effectiveness_metrics=payload_data.get("effectiveness_metrics"),
                        user_rating=payload_data.get("user_rating", 0.0),
                        user_feedback_count=payload_data.get("user_feedback_count", 0),
                        tags=payload_data.get("tags", []),
                        author=payload_data.get("author"),
                        source=payload_data.get("source"),
                        references=payload_data.get("references", []),
                        version=payload_data.get("version", "1.0.0"),
                        is_active=payload_data.get("is_active", True),
                        is_deprecated=payload_data.get("is_deprecated", False),
                        deprecation_reason=payload_data.get("deprecation_reason"),
                        requires_secondary_confirmation=payload_data.get("requires_secondary_confirmation", False),
                        risk_level=payload_data.get("risk_level", "low"),
                    )

                    session.add(db_obj)
                    imported += 1

                except Exception as e:
                    failed += 1
                    errors.append(f"{payload_data.get('id', 'unknown')}: {str(e)}")

            await session.commit()

        logger.info(f"Bulk import complete: {imported} imported, {failed} failed")

        return {
            "imported": imported,
            "failed": failed,
            "errors": errors[:10],
        }

    async def infer_framework_mappings(
        self,
        category: AttackCategory,
        template: str,
        description: str,
        tags: List[str],
        subcategory: Optional[str] = None,
        complexity: Optional[str] = None,
        risk_level: Optional[str] = None,
    ) -> Dict[FrameworkMapping, List[str]]:
        """
        Infer framework mappings for a payload based on its characteristics.
        """
        return self.mapping_service.infer_mappings(
            category=category,
            template=template,
            description=description,
            tags=tags,
            subcategory=subcategory,
            complexity=complexity,
            risk_level=risk_level,
        )

    def get_framework_taxonomy(self) -> Dict[str, Any]:
        """Get the framework taxonomy summary."""
        return self.mapping_service.get_taxonomy_summary()

    def validate_framework_mapping(
        self, framework: FrameworkMapping, mapping_items: List[str]
    ) -> Dict[str, Any]:
        """Validate a framework mapping against taxonomy definitions."""
        return self.mapping_service.validate_mapping(framework, mapping_items)

    def get_framework_mapping_for_category(
        self, category: AttackCategory, framework: FrameworkMapping
    ) -> List[str]:
        """Get the default framework mapping for a specific category."""
        return self.mapping_service.get_framework_mapping_for_category(category, framework)

    def _slugify(self, text: str) -> str:
        """Convert text to URL-friendly slug"""
        slug = text.lower().replace(" ", "-")
        slug = re.sub(r"[^a-z0-9-]", "", slug)
        slug = re.sub(r"-+", "-", slug)
        slug = slug.strip("-")
        return slug


# Singleton instance
_payload_service: Optional[PayloadLibraryService] = None


def get_payload_library() -> PayloadLibraryService:
    """Get the singleton PayloadLibraryService instance"""
    global _payload_service
    if _payload_service is None:
        _payload_service = PayloadLibraryService()
    return _payload_service
