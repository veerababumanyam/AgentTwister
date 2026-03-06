"""
Payload Library API Routes

FastAPI endpoints for managing security testing payload templates.
These routes provide CRUD operations, search, and filtering functionality.
"""

import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.services.payload_library import get_payload_library
from app.models.payload import (
    PayloadTemplate,
    PayloadTemplateCreate,
    PayloadTemplateUpdate,
    PayloadSearchFilters,
    PayloadRenderRequest,
    PayloadRenderResponse,
    AttackCategory,
    ComplexityLevel,
    FrameworkMapping,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/payloads",
    tags=["Payload Library"],
    responses={404: {"description": "Not found"}},
)


class StandardResponse(BaseModel):
    """Standard API response wrapper"""

    success: bool
    message: Optional[str] = None
    data: Optional[Any] = None
    errors: Optional[List[str]] = None


class PaginatedResponse(BaseModel):
    """Paginated API response"""

    success: bool
    data: List[Any]
    total: int
    page: int
    per_page: int
    has_more: bool


class FrameworkMappingInferRequest(BaseModel):
    """Request model for framework mapping inference"""

    category: AttackCategory
    template: str
    description: str
    tags: List[str] = Field(default_factory=list)
    subcategory: Optional[str] = None
    complexity: Optional[str] = None
    risk_level: Optional[str] = None


class FrameworkMappingValidateRequest(BaseModel):
    """Request model for framework mapping validation"""

    framework: FrameworkMapping
    mapping_items: List[str]


# Dependency to get payload library service
async def payload_service():
    return get_payload_library()


@router.get("/", response_model=Dict[str, Any])
async def list_payloads(
    limit: int = Query(50, ge=1, le=200, description="Number of results per page"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    active_only: bool = Query(True, description="Only return active payloads"),
    service=Depends(payload_service),
):
    """
    List all payload templates with pagination.

    Returns a paginated list of payload templates ordered by name.
    """
    try:
        payloads = await service.list_all(limit=limit, offset=offset, active_only=active_only)

        # Get total count (approximate - for exact count, would need a counter collection)
        total = len(payloads) + offset if len(payloads) == limit else offset + len(payloads)

        return {
            "success": True,
            "data": [p.model_dump() for p in payloads],
            "total": total,
            "page": (offset // limit) + 1 if limit > 0 else 1,
            "per_page": limit,
            "has_more": len(payloads) == limit,
        }
    except Exception as e:
        logger.error(f"Error listing payloads: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search", response_model=Dict[str, Any])
async def search_payloads(
    q: Optional[str] = Query(None, description="Full-text search query"),
    category: Optional[AttackCategory] = Query(None, description="Filter by attack category"),
    subcategory: Optional[str] = Query(None, description="Filter by subcategory"),
    complexity: Optional[ComplexityLevel] = Query(None, description="Filter by complexity level"),
    target_framework: Optional[str] = Query(None, description="Filter by target framework"),
    target_model: Optional[str] = Query(None, description="Filter by target model"),
    tags: Optional[str] = Query(None, description="Comma-separated list of tags to filter by"),
    risk_level: Optional[str] = Query(None, description="Filter by risk level"),
    min_effectiveness: Optional[float] = Query(None, ge=0, le=1, description="Minimum success rate"),
    framework_mapping: Optional[FrameworkMapping] = Query(None, description="Filter by framework mapping"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of results"),
    service=Depends(payload_service),
):
    """
    Search payload templates using filters and full-text search.

    Supports filtering by multiple criteria and full-text search across
    name, description, and template content.
    """
    try:
        # Parse tags if provided
        tag_list = None
        if tags:
            tag_list = [t.strip() for t in tags.split(",")]

        filters = PayloadSearchFilters(
            category=category,
            subcategory=subcategory,
            complexity=complexity,
            target_framework=target_framework,
            target_model=target_model,
            tags=tag_list,
            risk_level=risk_level,
            min_effectiveness=min_effectiveness,
            framework_mapping=framework_mapping,
            is_active=True,
        )

        # If full-text query is provided, use that; otherwise use filters
        if q:
            payloads = await service.full_text_search(query=q, limit=limit)
        else:
            payloads = await service.search(filters=filters, limit=limit)

        return {
            "success": True,
            "data": [p.model_dump() for p in payloads],
            "total": len(payloads),
            "query": {
                "q": q,
                "category": category.value if category else None,
                "complexity": complexity.value if complexity else None,
                "tags": tag_list,
            },
        }
    except Exception as e:
        logger.error(f"Error searching payloads: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories", response_model=Dict[str, Any])
async def get_categories(
    service=Depends(payload_service),
):
    """
    Get payload counts by OWASP LLM Top-10 category.

    Returns the distribution of payloads across attack categories.
    """
    try:
        categories = await service.get_categories()

        return {
            "success": True,
            "data": categories,
        }
    except Exception as e:
        logger.error(f"Error getting categories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/category/{category}", response_model=Dict[str, Any])
async def get_by_category(
    category: AttackCategory,
    limit: int = Query(100, ge=1, le=500),
    service=Depends(payload_service),
):
    """
    Get all payloads in a specific OWASP LLM Top-10 category.
    """
    try:
        payloads = await service.get_by_category(category)

        return {
            "success": True,
            "data": [p.model_dump() for p in payloads[:limit]],
            "category": category.value,
            "total": len(payloads),
        }
    except Exception as e:
        logger.error(f"Error getting payloads by category: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{payload_id}", response_model=Dict[str, Any])
async def get_payload(
    payload_id: str,
    service=Depends(payload_service),
):
    """
    Get a specific payload template by ID.
    """
    try:
        payload = await service.get_by_id(payload_id)

        if not payload:
            raise HTTPException(status_code=404, detail="Payload not found")

        return {
            "success": True,
            "data": payload.model_dump(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting payload: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/slug/{slug}", response_model=Dict[str, Any])
async def get_payload_by_slug(
    slug: str,
    service=Depends(payload_service),
):
    """
    Get a specific payload template by slug.
    """
    try:
        payload = await service.get_by_slug(slug)

        if not payload:
            raise HTTPException(status_code=404, detail="Payload not found")

        return {
            "success": True,
            "data": payload.model_dump(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting payload by slug: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_payload(
    payload_create: PayloadTemplateCreate,
    service=Depends(payload_service),
):
    """
    Create a new payload template.

    Requires proper authorization. The payload will be validated
    and assigned a unique ID.
    """
    try:
        payload = await service.create_payload(payload_create)

        return {
            "success": True,
            "message": "Payload created successfully",
            "data": payload.model_dump(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating payload: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{payload_id}", response_model=Dict[str, Any])
async def update_payload(
    payload_id: str,
    payload_update: PayloadTemplateUpdate,
    service=Depends(payload_service),
):
    """
    Update an existing payload template.

    Only the fields specified in the request body will be updated.
    """
    try:
        payload = await service.update_payload(payload_id, payload_update)

        if not payload:
            raise HTTPException(status_code=404, detail="Payload not found")

        return {
            "success": True,
            "message": "Payload updated successfully",
            "data": payload.model_dump(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating payload: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{payload_id}", response_model=Dict[str, Any])
async def delete_payload(
    payload_id: str,
    hard_delete: bool = Query(False, description="Permanently delete instead of soft delete"),
    service=Depends(payload_service),
):
    """
    Delete a payload template.

    By default, performs a soft delete (marks as inactive).
    Set hard_delete=true to permanently remove the payload.
    """
    try:
        deleted = await service.delete_payload(payload_id, hard_delete=hard_delete)

        if not deleted:
            raise HTTPException(status_code=404, detail="Payload not found")

        return {
            "success": True,
            "message": "Payload deleted successfully" + (" (hard delete)" if hard_delete else " (soft delete)"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting payload: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/render", response_model=Dict[str, Any])
async def render_payload(
    request: PayloadRenderRequest,
    service=Depends(payload_service),
):
    """
    Render a payload template with specific variable values.

    Returns the rendered payload with warnings about any issues.
    """
    try:
        # Get the template
        payload = await service.get_by_id(request.template_id)
        if not payload:
            raise HTTPException(status_code=404, detail="Payload template not found")

        # Render the template
        rendered = payload.template
        warnings = []

        # Check for missing variables
        provided_vars = set(request.variable_values.keys())
        required_vars = set(payload.variables)

        missing_vars = required_vars - provided_vars
        if missing_vars:
            warnings.append(f"Missing variables: {', '.join(missing_vars)}")

        extra_vars = provided_vars - required_vars
        if extra_vars:
            warnings.append(f"Unused variables: {', '.join(extra_vars)}")

        # Substitute variables
        import re

        for var_name, var_value in request.variable_values.items():
            pattern = r"\{\{" + re.escape(var_name) + r"\}\}"
            rendered = re.sub(pattern, str(var_value), rendered)

        # Check for unreplaced placeholders
        unreplaced = re.findall(r"\{\{(\w+)\}\}", rendered)
        if unreplaced:
            warnings.append(f"Unreplaced placeholders: {', '.join(set(unreplaced))}")

        return {
            "success": True,
            "data": {
                "rendered_payload": rendered,
                "template_id": payload.id,
                "template_name": payload.name,
                "warnings": warnings,
                "requires_confirmation": payload.requires_secondary_confirmation,
                "risk_level": payload.risk_level,
                "category": payload.category.value,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rendering payload: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{payload_id}/feedback", response_model=Dict[str, Any])
async def add_feedback(
    payload_id: str,
    rating: float = Query(..., ge=0, le=5, description="Rating from 0 to 5"),
    service=Depends(payload_service),
):
    """
    Add user feedback rating to a payload template.

    Ratings are used to improve the payload library and help
    other researchers select effective payloads.
    """
    try:
        payload = await service.add_feedback(payload_id, rating)

        if not payload:
            raise HTTPException(status_code=404, detail="Payload not found")

        return {
            "success": True,
            "message": "Feedback recorded successfully",
            "data": {
                "payload_id": payload.id,
                "new_rating": payload.user_rating,
                "feedback_count": payload.user_feedback_count,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{payload_id}/usage", response_model=Dict[str, Any])
async def record_usage(
    payload_id: str,
    success: bool = Query(..., description="Whether the payload was successful"),
    target_framework: Optional[str] = Query(None, description="Target framework tested"),
    detection_time_ms: Optional[int] = Query(None, description="Time to detection in ms"),
    service=Depends(payload_service),
):
    """
    Record payload usage for effectiveness tracking.

    This endpoint is used internally to track which payloads
    are effective against which targets.
    """
    try:
        await service.record_usage(payload_id, success, target_framework, detection_time_ms)

        return {
            "success": True,
            "message": "Usage recorded successfully",
        }
    except Exception as e:
        logger.error(f"Error recording usage: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import/bulk", response_model=Dict[str, Any])
async def bulk_import(
    payloads: List[Dict[str, Any]],
    service=Depends(payload_service),
):
    """
    Bulk import payload templates.

    Used for initial seeding and updates from external sources.
    Requires proper authorization.
    """
    try:
        result = await service.bulk_import(payloads)

        return {
            "success": True,
            "message": f"Import complete: {result['imported']} imported, {result['failed']} failed",
            "data": result,
        }
    except Exception as e:
        logger.error(f"Error during bulk import: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Framework Mapping Endpoints

@router.get("/framework/taxonomy", response_model=Dict[str, Any])
async def get_framework_taxonomy(
    service=Depends(payload_service),
):
    """
    Get framework taxonomy summary.

    Returns information about available framework mappings
    and their coverage of OWASP LLM Top-10 categories.
    """
    try:
        taxonomy = service.get_framework_taxonomy()

        return {
            "success": True,
            "data": taxonomy,
        }
    except Exception as e:
        logger.error(f"Error getting framework taxonomy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/framework/infer", response_model=Dict[str, Any])
async def infer_framework_mappings(
    request: FrameworkMappingInferRequest,
    service=Depends(payload_service),
):
    """
    Infer framework mappings for a payload based on its characteristics.

    This endpoint analyzes the payload content and suggests appropriate
    framework mappings for OWASP ASI, MITRE ATLAS, NIST AI RMF, ISO 42001, and EU AI Act.
    """
    try:
        mappings = await service.infer_framework_mappings(
            category=request.category,
            template=request.template,
            description=request.description,
            tags=request.tags,
            subcategory=request.subcategory,
            complexity=request.complexity,
            risk_level=request.risk_level,
        )

        # Convert enum keys to strings for JSON serialization
        serializable_mappings = {
            framework.value: items for framework, items in mappings.items()
        }

        return {
            "success": True,
            "data": {
                "inferred_mappings": serializable_mappings,
                "category": request.category.value,
            },
        }
    except Exception as e:
        logger.error(f"Error inferring framework mappings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/framework/category/{category}", response_model=Dict[str, Any])
async def get_framework_mapping_for_category(
    category: AttackCategory,
    framework: FrameworkMapping,
    service=Depends(payload_service),
):
    """
    Get the default framework mapping for a specific OWASP LLM Top-10 category.

    Returns the standard framework mappings for a given category,
    useful for understanding how categories map to compliance frameworks.
    """
    try:
        mappings = service.get_framework_mapping_for_category(category, framework)

        return {
            "success": True,
            "data": {
                "category": category.value,
                "framework": framework.value,
                "mappings": mappings,
            },
        }
    except Exception as e:
        logger.error(f"Error getting framework mapping for category: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/framework/validate", response_model=Dict[str, Any])
async def validate_framework_mapping(
    request: FrameworkMappingValidateRequest,
    service=Depends(payload_service),
):
    """
    Validate a framework mapping against taxonomy definitions.

    Checks if the provided mapping items are recognized in the taxonomy,
    helping ensure consistency and correctness of framework mappings.
    """
    try:
        validation_result = service.validate_framework_mapping(
            request.framework, request.mapping_items
        )

        return {
            "success": True,
            "data": {
                "framework": request.framework.value,
                "is_valid": validation_result["valid"],
                "unknown_items": validation_result["unknown_items"],
                "warnings": validation_result["warnings"],
            },
        }
    except Exception as e:
        logger.error(f"Error validating framework mapping: {e}")
        raise HTTPException(status_code=500, detail=str(e))
