"""
Document Generation API Routes

FastAPI endpoints for generating adversarial DOCX and PDF documents with
stealth payload embedding for authorized security testing.

These endpoints are designed exclusively for:
- Authorized penetration testing
- Security research
- Red team exercises
- Compliance audits
"""

import base64
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query, Depends, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from app.models.payload import (
    DocumentGenerationRequest,
    DocumentGenerationResponse,
    DocumentTemplate,
    PayloadEmbedding,
    StealthTechnique,
    PDFGenerationRequest,
    PDFGenerationResponse,
    PDFPayloadEmbedding,
    PDFStealthTechnique,
    DualViewPreview,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/documents",
    tags=["Document Generation"],
    responses={404: {"description": "Not found"}},
)


class StandardResponse(BaseModel):
    """Standard API response wrapper"""

    success: bool
    message: Optional[str] = None
    data: Optional[Any] = None
    errors: Optional[List[str]] = None


class DocumentEmbedRequest(BaseModel):
    """Request to embed a payload in an existing document"""

    document_bytes: str = Field(..., description="Base64-encoded DOCX file")
    payload: str = Field(..., description="Payload to embed")
    technique: StealthTechnique = Field(
        default=StealthTechnique.FONT_COLOR_MATCH,
        description="Stealth technique to use"
    )


class TemplateApplyRequest(BaseModel):
    """Request to apply a template to content"""

    content: str = Field(..., description="Content to format")
    template: DocumentTemplate = Field(
        default=DocumentTemplate.BUSINESS_MEMO,
        description="Template to apply"
    )


class DocumentValidateRequest(BaseModel):
    """Request to validate a document configuration"""

    visible_content: str = Field(..., description="Visible content for document")
    payload_embeddings: List[PayloadEmbedding] = Field(
        default_factory=list,
        description="Payloads to embed"
    )
    template: DocumentTemplate = Field(
        default=DocumentTemplate.BUSINESS_MEMO,
        description="Document template"
    )


@router.post("/generate", response_model=Dict[str, Any])
async def generate_document(
    request: DocumentGenerationRequest,
    return_base64: bool = Query(True, description="Return document as base64"),
):
    """
    Generate an adversarial DOCX document with stealth payloads.

    This endpoint creates a professional-looking DOCX document with
    payloads embedded using the specified stealth techniques.

    **Security Notice**: All generated documents include metadata
    indicating they are for security testing purposes.

    **Supported Stealth Techniques**:
    - `font_color_match`: Text color matches background (white on white)
    - `zero_width_unicode`: Zero-width character encoding
    - `white_on_white`: White text on white background with highlight
    - `tiny_font`: 1pt font size
    - `hidden_text_property`: Using Word's vanish property
    - `metadata_injection`: Hidden in document metadata
    - `footnote_embedding`: Hidden in footnotes
    - `comment_injection`: Hidden as document comments
    - `header_footer_hidden`: Hidden in headers/footers
    - `invisible_table`: Table with invisible borders
    - `overlay_text`: Overlay text matching visible content
    """
    try:
        from app.agents.tools import ToolFactory

        docx_tool = ToolFactory.get_docx_generator()

        # Convert payload embeddings for the tool
        payload_embeddings = [
            {
                "payload": pe.payload,
                "technique": pe.technique.value,
                "position": pe.position,
                "anchor_text": pe.anchor_text,
                "additional_config": pe.additional_config,
            }
            for pe in request.payload_embeddings
        ]

        # Generate the document
        result = await docx_tool.call(
            visible_content=request.visible_content,
            payload_embeddings=payload_embeddings,
            template=request.template.value,
            metadata=request.metadata,
            filename=request.filename,
            return_base64=return_base64,
        )

        return {
            "success": True,
            "message": "Document generated successfully",
            "data": result,
        }

    except Exception as e:
        logger.error(f"Error generating document: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/embed", response_model=Dict[str, Any])
async def embed_payload(request: DocumentEmbedRequest):
    """
    Embed a payload into an existing document.

    Takes a base64-encoded DOCX file and embeds the specified payload
    using the chosen stealth technique.
    """
    try:
        from app.agents.document_formatter import DocumentFormatterAgent
        from app.agents.base_agent import AgentContext
        from io import BytesIO

        # Decode document
        document_bytes = base64.b64decode(request.document_bytes)

        # Create agent and process
        agent = DocumentFormatterAgent()
        context = AgentContext(session_id=f"embed_{datetime.utcnow().timestamp()}")

        result = await agent.embed_payload_in_document(
            context=context,
            document=document_bytes,
            payload=request.payload,
            technique=request.technique,
        )

        return {
            "success": True,
            "message": "Payload embedded successfully",
            "data": result,
        }

    except Exception as e:
        logger.error(f"Error embedding payload: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/apply-template", response_model=Dict[str, Any])
async def apply_template(request: TemplateApplyRequest):
    """
    Apply a document template to content.

    Formats the given content according to the specified document template,
    returning the formatted content with appropriate structure.
    """
    try:
        from app.agents.document_formatter import DocumentFormatterAgent
        from app.agents.base_agent import AgentContext

        agent = DocumentFormatterAgent()
        context = AgentContext(session_id=f"template_{datetime.utcnow().timestamp()}")

        result = await agent.apply_template(
            context=context,
            content=request.content,
            template=request.template,
        )

        return {
            "success": True,
            "message": "Template applied successfully",
            "data": result,
        }

    except Exception as e:
        logger.error(f"Error applying template: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate", response_model=Dict[str, Any])
async def validate_document(request: DocumentValidateRequest):
    """
    Validate a document configuration.

    Checks if the document configuration is valid and provides
    a quality score along with any issues or warnings.
    """
    try:
        from app.agents.document_formatter import DocumentFormatterAgent
        from app.agents.base_agent import AgentContext

        agent = DocumentFormatterAgent()
        context = AgentContext(session_id=f"validate_{datetime.utcnow().timestamp()}")

        document_data = {
            "visible_content": request.visible_content,
            "payload_embeddings": [
                pe.model_dump() for pe in request.payload_embeddings
            ],
            "template": request.template.value,
            "include_security_metadata": True,
        }

        result = await agent.validate_document(
            context=context,
            document_data=document_data,
        )

        return {
            "success": True,
            "message": "Document validated",
            "data": result,
        }

    except Exception as e:
        logger.error(f"Error validating document: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates", response_model=Dict[str, Any])
async def list_templates():
    """
    List available document templates.

    Returns all available document templates with their descriptions
    and typical use cases.
    """
    templates = [
        {
            "value": "business_memo",
            "name": "Business Memo",
            "description": "Standard business memorandum format",
            "structure": "memo",
        },
        {
            "value": "technical_report",
            "name": "Technical Report",
            "description": "Technical documentation format",
            "structure": "report",
        },
        {
            "value": "financial_statement",
            "name": "Financial Statement",
            "description": "Financial reporting format",
            "structure": "financial",
        },
        {
            "value": "internal_policy",
            "name": "Internal Policy",
            "description": "Internal policy document format",
            "structure": "policy",
        },
        {
            "value": "project_proposal",
            "name": "Project Proposal",
            "description": "Project proposal format",
            "structure": "proposal",
        },
        {
            "value": "meeting_minutes",
            "name": "Meeting Minutes",
            "description": "Meeting minutes format",
            "structure": "minutes",
        },
        {
            "value": "email_attachment",
            "name": "Email Attachment",
            "description": "Email-style document format",
            "structure": "email",
        },
        {
            "value": "resume",
            "name": "Resume/CV",
            "description": "Resume or CV format",
            "structure": "resume",
        },
        {
            "value": "academic_paper",
            "name": "Academic Paper",
            "description": "Academic paper format",
            "structure": "academic",
        },
        {
            "value": "invoice",
            "name": "Invoice",
            "description": "Invoice format",
            "structure": "invoice",
        },
    ]

    return {
        "success": True,
        "data": templates,
    }


@router.get("/techniques", response_model=Dict[str, Any])
async def list_stealth_techniques():
    """
    List available stealth techniques.

    Returns all available stealth embedding techniques with descriptions
    and effectiveness notes.
    """
    techniques = [
        {
            "value": "font_color_match",
            "name": "Font Color Match",
            "description": "Text color matches background color (default: white on white)",
            "effectiveness": "High - Invisible to humans, readable to machines",
            "detectability": "Low - Requires careful inspection to detect",
        },
        {
            "value": "zero_width_unicode",
            "name": "Zero-Width Unicode",
            "description": "Payload encoded as zero-width Unicode characters",
            "effectiveness": "Very High - Completely invisible",
            "detectability": "Very Low - Only detectable programmatically",
        },
        {
            "value": "white_on_white",
            "name": "White on White",
            "description": "White text on white background with white highlight",
            "effectiveness": "High - Invisible to humans",
            "detectability": "Low - May be detected by copy-paste",
        },
        {
            "value": "tiny_font",
            "name": "Tiny Font",
            "description": "Payload in 1pt font size",
            "effectiveness": "Medium - May be visible on close inspection",
            "detectability": "Medium - Can be found by zooming",
        },
        {
            "value": "hidden_text_property",
            "name": "Hidden Text Property",
            "description": "Using Word's vanish (hidden) property",
            "effectiveness": "High - Hidden in Word, may show in export",
            "detectability": "Medium - Revealed when copying text",
        },
        {
            "value": "metadata_injection",
            "name": "Metadata Injection",
            "description": "Payload hidden in document metadata fields",
            "effectiveness": "High - Not visible in main content",
            "detectability": "Low - Requires inspecting document properties",
        },
        {
            "value": "footnote_embedding",
            "name": "Footnote Embedding",
            "description": "Payload hidden as invisible footnote",
            "effectiveness": "Medium - Footnotes are often overlooked",
            "detectability": "Medium - May be found in review mode",
        },
        {
            "value": "comment_injection",
            "name": "Comment Injection",
            "description": "Payload hidden as document comment",
            "effectiveness": "Medium - Comments hidden by default",
            "detectability": "Medium - Visible in review mode",
        },
        {
            "value": "header_footer_hidden",
            "name": "Header/Footer Hidden",
            "description": "Payload hidden in invisible header/footer",
            "effectiveness": "High - Headers/footers often overlooked",
            "detectability": "Low - Requires inspecting header/footer",
        },
        {
            "value": "invisible_table",
            "name": "Invisible Table",
            "description": "Payload in table with invisible borders",
            "effectiveness": "Medium - Tables common in documents",
            "detectability": "Medium - Table structure still visible",
        },
        {
            "value": "overlay_text",
            "name": "Overlay Text",
            "description": "Payload overlaid on matching visible text",
            "effectiveness": "High - Masks payload with visible content",
            "detectability": "Medium - May show as duplication",
        },
    ]

    return {
        "success": True,
        "data": techniques,
    }


@router.get("/download/{document_id}", response_class=Response)
async def download_document(document_id: str):
    """
    Download a generated document by ID.

    Returns the DOCX file for download. Documents are stored
    in session memory and expire after the session ends.
    """
    try:
        from app.agents.document_formatter import DocumentFormatterAgent
        from app.agents.base_agent import AgentContext

        agent = DocumentFormatterAgent()
        context = AgentContext(session_id=f"download_{document_id}")

        # Try to retrieve from memory
        document_content = await agent.load_from_memory(
            key=f"document_{document_id}",
            context=context,
        )

        if not document_content:
            raise HTTPException(
                status_code=404,
                detail="Document not found or has expired"
            )

        # Decode and return
        document_bytes = base64.b64decode(document_content)

        return Response(
            content=document_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f"attachment; filename=document_{document_id}.docx"
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading document: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=Dict[str, Any])
async def health_check():
    """
    Health check endpoint for the document generation service.

    Returns the status of the document generation functionality.
    """
    try:
        from app.agents.tools import ToolFactory

        # Try to get the tool to verify it's working
        docx_tool = ToolFactory.get_docx_generator()

        return {
            "success": True,
            "status": "healthy",
            "service": "document_generation",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "status": "unhealthy",
                "error": str(e),
            }
        )


# ============================================================
# PDF GENERATION ENDPOINTS
# ============================================================

@router.post("/pdf/generate", response_model=Dict[str, Any])
async def generate_pdf_document(
    request: PDFGenerationRequest,
    return_base64: bool = Query(True, description="Return PDF as base64"),
):
    """
    Generate an adversarial PDF document with stealth payloads.

    This endpoint creates a professional-looking PDF document with
    payloads embedded using the specified stealth techniques.

    **Security Notice**: All generated documents include metadata
    indicating they are for security testing purposes.

    **Supported Stealth Techniques**:
    - `font_color_match`: Text color matches background color
    - `zero_width_unicode`: Zero-width character encoding
    - `white_on_white`: White text on white background
    - `tiny_font`: 1pt font size
    - `hidden_layer`: PDF Optional Content Groups (layers)
    - `annotation_hidden`: Hidden PDF annotations
    - `invisible_form_field`: Hidden form fields
    - `metadata_injection`: Hidden in document metadata

    **Dual-View Preview**:
    Set `generate_dual_view=True` to receive both human-visible and
    LLM-parsed views for verification.
    """
    try:
        from app.agents.tools import ToolFactory

        pdf_tool = ToolFactory.get_pdf_generator()

        # Convert payload embeddings for the tool
        payload_embeddings = [
            {
                "payload": pe.payload,
                "technique": pe.technique.value,
                "position": pe.position,
                "anchor_text": pe.anchor_text,
                "additional_config": pe.additional_config,
            }
            for pe in request.payload_embeddings
        ]

        # Generate the PDF
        result = await pdf_tool.call(
            visible_content=request.visible_content,
            payload_embeddings=payload_embeddings,
            template=request.template.value,
            metadata=request.metadata,
            filename=request.filename,
            return_base64=return_base64,
            generate_dual_view=request.generate_dual_view,
        )

        return {
            "success": True,
            "message": "PDF document generated successfully",
            "data": result,
        }

    except Exception as e:
        logger.error(f"Error generating PDF: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pdf/dual-view", response_model=Dict[str, Any])
async def generate_pdf_dual_view(
    request: PDFGenerationRequest,
):
    """
    Generate a PDF with dual-view preview.

    Returns both the human-visible view (what a person sees) and
    the LLM-parsed view (what an LLM extracts) for verification
    of stealth embedding effectiveness.
    """
    try:
        from app.agents.tools import ToolFactory

        pdf_tool = ToolFactory.get_pdf_generator()

        # Force dual-view generation
        payload_embeddings = [
            {
                "payload": pe.payload,
                "technique": pe.technique.value,
                "position": pe.position,
                "anchor_text": pe.anchor_text,
                "additional_config": pe.additional_config,
            }
            for pe in request.payload_embeddings
        ]

        result = await pdf_tool.call(
            visible_content=request.visible_content,
            payload_embeddings=payload_embeddings,
            template=request.template.value,
            metadata=request.metadata,
            filename=request.filename,
            return_base64=True,
            generate_dual_view=True,
        )

        return {
            "success": True,
            "message": "PDF dual-view generated successfully",
            "data": result,
        }

    except Exception as e:
        logger.error(f"Error generating PDF dual-view: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pdf/extract", response_model=Dict[str, Any])
async def extract_pdf_payloads(
    request: Dict[str, Any],
):
    """
    Extract embedded payloads from a PDF document.

    Analyzes a PDF document and attempts to extract any
    stealth-embedded payloads for verification.

    Request body:
        document_bytes: Base64-encoded PDF file
    """
    document_bytes = request.get("document_bytes")
    if not document_bytes:
        raise HTTPException(status_code=400, detail="document_bytes is required")
    try:
        import io

        # Decode document
        pdf_bytes = base64.b64decode(document_bytes)

        # Try to extract text and analyze
        extracted_content = []

        try:
            # Try PyPDF2 for extraction
            import PyPDF2

            pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))

            for page_num, page in enumerate(pdf_reader.pages):
                text = page.extract_text()
                if text:
                    extracted_content.append({
                        "page": page_num + 1,
                        "text": text[:500],  # First 500 chars
                    })

        except ImportError:
            # Fallback: basic analysis
            extracted_content.append({
                "note": "PyPDF2 not available for detailed extraction",
            })

        return {
            "success": True,
            "message": "PDF extraction completed",
            "data": {
                "extracted_content": extracted_content,
                "total_pages": len(extracted_content),
            },
        }

    except Exception as e:
        logger.error(f"Error extracting PDF: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pdf/techniques", response_model=Dict[str, Any])
async def list_pdf_stealth_techniques():
    """
    List available PDF stealth techniques.

    Returns all available stealth embedding techniques for PDF
    with descriptions and effectiveness notes.
    """
    techniques = [
        {
            "value": "font_color_match",
            "name": "Font Color Match",
            "description": "Text color matches background color (default: white on white)",
            "effectiveness": "High - Invisible to humans, readable to machines",
            "detectability": "Low - Requires careful inspection to detect",
        },
        {
            "value": "zero_width_unicode",
            "name": "Zero-Width Unicode",
            "description": "Payload encoded as zero-width Unicode characters",
            "effectiveness": "Very High - Completely invisible",
            "detectability": "Very Low - Only detectable programmatically",
        },
        {
            "value": "white_on_white",
            "name": "White on White",
            "description": "White text on white background",
            "effectiveness": "High - Invisible to humans",
            "detectability": "Low - May be detected by copy-paste",
        },
        {
            "value": "tiny_font",
            "name": "Tiny Font",
            "description": "Payload in 1pt font size",
            "effectiveness": "Medium - May be visible on close inspection",
            "detectability": "Medium - Can be found by zooming",
        },
        {
            "value": "hidden_layer",
            "name": "Hidden Layer (OCG)",
            "description": "PDF Optional Content Group (layer) set to invisible",
            "effectiveness": "Very High - Hidden in PDF layer structure",
            "detectability": "Very Low - Requires PDF inspection tools",
        },
        {
            "value": "annotation_hidden",
            "name": "Hidden Annotation",
            "description": "Payload hidden as invisible PDF annotation",
            "effectiveness": "High - Hidden in annotation structure",
            "detectability": "Low - Requires annotation inspection",
        },
        {
            "value": "invisible_form_field",
            "name": "Invisible Form Field",
            "description": "Payload in invisible form field",
            "effectiveness": "Medium - Form fields may be overlooked",
            "detectability": "Medium - Visible in form field inspection",
        },
        {
            "value": "metadata_injection",
            "name": "Metadata Injection",
            "description": "Payload hidden in document metadata fields",
            "effectiveness": "High - Not visible in main content",
            "detectability": "Low - Requires inspecting document properties",
        },
    ]

    return {
        "success": True,
        "data": techniques,
    }


@router.get("/download-pdf/{document_id}", response_class=Response)
async def download_pdf_document(document_id: str):
    """
    Download a generated PDF document by ID.

    Returns the PDF file for download. Documents are stored
    in session memory and expire after the session ends.
    """
    try:
        from app.agents.document_formatter import DocumentFormatterAgent
        from app.agents.base_agent import AgentContext

        agent = DocumentFormatterAgent()
        context = AgentContext(session_id=f"download_pdf_{document_id}")

        # Try to retrieve from memory
        document_content = await agent.load_from_memory(
            key=f"pdf_document_{document_id}",
            context=context,
        )

        if not document_content:
            raise HTTPException(
                status_code=404,
                detail="PDF document not found or has expired"
            )

        # Decode and return
        document_bytes = base64.b64decode(document_content)

        return Response(
            content=document_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=document_{document_id}.pdf"
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading PDF: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
