"""
PDF Generator Tool

Creates adversarial PDF documents with stealth payload embedding for
authorized security testing of LLM document ingestion systems.

This tool is designed exclusively for:
- Authorized penetration testing
- Security research
- Red team exercises
- Compliance audits

All generated documents include metadata indicating their test nature.
"""

import base64
import logging
import re
from datetime import datetime
from enum import Enum
from io import BytesIO
from typing import Any, Dict, List, Optional, Union

from . import BaseTool

logger = logging.getLogger(__name__)


# Zero-width Unicode characters for stealth embedding
ZERO_WIDTH_CHARS = {
    "zero_width_space": "\u200B",
    "zero_width_non_joiner": "\u200C",
    "zero_width_joiner": "\u200D",
    "left_to_right_mark": "\u200E",
    "right_to_left_mark": "\u200F",
    "word_joiner": "\u2060",
    "invisible_plus": "\u2064",
}


class PDFDocumentStyle(str, Enum):
    """Predefined PDF document styles for various document types."""

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


class PDFGeneratorTool(BaseTool):
    """
    Tool for generating adversarial PDF documents with stealth payloads.

    Supports multiple stealth techniques:
    - Font color matching (text color = background color)
    - Zero-width Unicode characters
    - White-on-white text
    - Tiny font (1pt)
    - Metadata injection
    - Hidden layer (PDF Optional Content)
    - Annotation-based embedding
    - Invisible form fields
    - Footer/Header hidden content
    """

    # Document templates with structure
    DOCUMENT_TEMPLATES = {
        PDFDocumentStyle.BUSINESS_MEMO: {
            "title": "MEMORANDUM",
            "headers": ["To:", "From:", "Date:", "Subject:"],
            "structure": "memo",
        },
        PDFDocumentStyle.TECHNICAL_REPORT: {
            "title": "TECHNICAL REPORT",
            "headers": ["Title:", "Author:", "Date:", "Document ID:"],
            "structure": "report",
        },
        PDFDocumentStyle.FINANCIAL_STATEMENT: {
            "title": "FINANCIAL STATEMENT",
            "headers": ["Period:", "Prepared By:", "Date:"],
            "structure": "financial",
        },
        PDFDocumentStyle.INTERNAL_POLICY: {
            "title": "INTERNAL POLICY",
            "headers": ["Policy Number:", "Effective Date:", "Department:"],
            "structure": "policy",
        },
        PDFDocumentStyle.PROJECT_PROPOSAL: {
            "title": "PROJECT PROPOSAL",
            "headers": ["Project:", "Submitted By:", "Date:"],
            "structure": "proposal",
        },
        PDFDocumentStyle.MEETING_MINUTES: {
            "title": "MEETING MINUTES",
            "headers": ["Meeting:", "Date:", "Attendees:", "Time:"],
            "structure": "minutes",
        },
        PDFDocumentStyle.EMAIL_ATTACHMENT: {
            "title": "",
            "headers": [],
            "structure": "email",
        },
        PDFDocumentStyle.RESUME: {
            "title": "",
            "headers": [],
            "structure": "resume",
        },
        PDFDocumentStyle.ACADEMIC_PAPER: {
            "title": "",
            "headers": ["Abstract", "Introduction", "Methodology"],
            "structure": "academic",
        },
        PDFDocumentStyle.INVOICE: {
            "title": "INVOICE",
            "headers": ["Invoice #:", "Date:", "Bill To:", "From:"],
            "structure": "invoice",
        },
    }

    def __init__(self):
        super().__init__(
            name="pdf_generator",
            description="Generate adversarial PDF documents with stealth payload embedding for security testing.",
        )

    def get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "visible_content": {
                    "type": "string",
                    "description": "The visible content that appears in the document",
                },
                "payload_embeddings": {
                    "type": "array",
                    "description": "List of payloads to embed with stealth techniques",
                    "items": {
                        "type": "object",
                        "properties": {
                            "payload": {
                                "type": "string",
                                "description": "The payload text to embed",
                            },
                            "technique": {
                                "type": "string",
                                "enum": [
                                    "font_color_match",
                                    "zero_width_unicode",
                                    "white_on_white",
                                    "tiny_font",
                                    "hidden_text_property",
                                    "metadata_injection",
                                    "footnote_embedding",
                                    "comment_injection",
                                    "header_footer_hidden",
                                    "invisible_table",
                                    "overlay_text",
                                    "hidden_layer",
                                    "annotation_hidden",
                                    "invisible_form_field",
                                ],
                                "description": "The stealth technique to use",
                            },
                            "position": {
                                "type": "string",
                                "enum": ["start", "end", "after_text", "before_text"],
                                "description": "Where to embed the payload",
                            },
                            "anchor_text": {
                                "type": "string",
                                "description": "Anchor text for position-based embedding",
                            },
                            "additional_config": {
                                "type": "object",
                                "description": "Additional configuration for the technique",
                            },
                        },
                        "required": ["payload", "technique"],
                    },
                },
                "template": {
                    "type": "string",
                    "enum": [s.value for s in PDFDocumentStyle],
                    "description": "Document template to use",
                },
                "metadata": {
                    "type": "object",
                    "description": "Custom document metadata",
                },
                "filename": {
                    "type": "string",
                    "description": "Output filename (without extension)",
                },
                "return_base64": {
                    "type": "boolean",
                    "description": "Return document as base64 encoded string",
                },
                "generate_dual_view": {
                    "type": "boolean",
                    "description": "Generate dual-view preview (human-visible vs LLM-parsed)",
                },
            },
            "required": ["visible_content"],
        }

    async def call(
        self,
        visible_content: str,
        payload_embeddings: Optional[List[Dict[str, Any]]] = None,
        template: str = "business_memo",
        metadata: Optional[Dict[str, str]] = None,
        filename: Optional[str] = None,
        return_base64: bool = True,
        generate_dual_view: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate an adversarial PDF document.

        Args:
            visible_content: The visible content in the document
            payload_embeddings: Payloads to embed with stealth techniques
            template: Document template style
            metadata: Custom document metadata
            filename: Output filename
            return_base64: Whether to return base64 encoded content
            generate_dual_view: Whether to generate dual-view preview

        Returns:
            Dict with generated document info
        """
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch, mm
            from reportlab.lib.colors import Color, white, black
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.enums import TA_LEFT, TA_CENTER
            from reportlab.pdfgen import canvas
        except ImportError:
            raise ImportError(
                "reportlab is required for PDF generation. "
                "Install it with: pip install reportlab"
            )

        # Parse template style
        try:
            style = PDFDocumentStyle(template)
        except ValueError:
            style = PDFDocumentStyle.BUSINESS_MEMO

        # Create PDF buffer
        buffer = BytesIO()

        # Build the PDF
        story, pdf_metadata, embedded_payloads, techniques_used = self._build_pdf_content(
            style, visible_content, payload_embeddings or [], metadata or {}
        )

        # Create PDF with metadata
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            **pdf_metadata
        )

        # Build the document
        doc.build(story, onFirstPage=self._on_first_page,
                 onLaterPages=self._on_later_pages)

        buffer.seek(0)
        file_content = buffer.read()
        file_size = len(file_content)

        # Generate dual view if requested
        dual_view_data = None
        if generate_dual_view:
            dual_view_data = self._generate_dual_view(
                visible_content, embedded_payloads
            )

        # Generate filename if not provided
        if not filename:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"document_{timestamp}"

        # Prepare response
        result = {
            "filename": f"{filename}.pdf",
            "file_size_bytes": file_size,
            "mime_type": "application/pdf",
            "template_used": style.value,
            "embedded_payloads_count": len(embedded_payloads),
            "stealth_techniques_used": techniques_used,
            "generated_at": datetime.utcnow().isoformat(),
        }

        if return_base64:
            result["content_base64"] = base64.b64encode(file_content).decode("ascii")

        if dual_view_data:
            result["dual_view"] = dual_view_data

        logger.info(
            f"Generated PDF document: {filename}.pdf "
            f"({file_size} bytes, {len(embedded_payloads)} payloads)"
        )

        return result

    def _build_pdf_content(
        self,
        style: PDFDocumentStyle,
        visible_content: str,
        payload_embeddings: List[Dict[str, Any]],
        metadata: Dict[str, str]
    ) -> tuple:
        """Build the PDF content, returning story, metadata, and embedded payloads."""
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.colors import white, black
        from reportlab.platypus import Paragraph, Spacer, Table
        from reportlab.lib.enums import TA_LEFT, TA_CENTER

        styles = getSampleStyleSheet()
        story = []
        embedded_payloads = []
        techniques_used = []

        # Custom styles
        title_style = ParagraphStyle(
            'Title1',
            parent=styles['Heading1'],
            fontSize=18,
            alignment=TA_CENTER,
            spaceAfter=12,
        )
        hidden_style = ParagraphStyle(
            'HiddenText',
            fontSize=10,
            textColor=white,
            leading=12,
        )
        tiny_style = ParagraphStyle(
            'TinyText',
            fontSize=1,
            leading=1,
        )

        template_info = self.DOCUMENT_TEMPLATES.get(
            style,
            self.DOCUMENT_TEMPLATES[PDFDocumentStyle.BUSINESS_MEMO]
        )

        # Add title
        if template_info.get("title"):
            story.append(Paragraph(template_info["title"], title_style))
            story.append(Spacer(1, 12))

        # Add header fields
        if template_info.get("headers"):
            for header in template_info["headers"]:
                text = f"<b>{header}</b>"
                story.append(Paragraph(text, styles['Normal']))
            story.append(Spacer(1, 12))

        # Add visible content
        paragraphs = visible_content.split("\n\n")
        for para_text in paragraphs:
            if para_text.strip():
                story.append(Paragraph(para_text.strip(), styles['Normal']))
                story.append(Spacer(1, 6))

        # Embed payloads using stealth techniques
        for embedding_config in payload_embeddings:
            try:
                technique = embedding_config.get("technique", "font_color_match")
                payload = embedding_config.get("payload", "")
                position = embedding_config.get("position", "end")
                anchor_text = embedding_config.get("anchor_text")
                additional_config = embedding_config.get("additional_config", {})

                # Apply the technique
                self._embed_payload_pdf(
                    story,
                    styles,
                    payload,
                    technique,
                    additional_config
                )

                techniques_used.append(technique)
                embedded_payloads.append(
                    payload[:100] + "..." if len(payload) > 100 else payload
                )

            except Exception as e:
                logger.warning(f"Failed to embed payload: {e}")
                # Continue with other payloads

        # Prepare PDF metadata
        pdf_metadata = {
            'title': metadata.get('title', f"{style.value.replace('_', ' ').title()}"),
            'author': metadata.get('author', 'Security Testing'),
            'subject': metadata.get('subject', '') + " | SECURITY TEST DOCUMENT - For authorized testing only",
            'keywords': metadata.get('keywords', 'SECURITY_TEST,AUTHORIZED_TESTING_ONLY'),
            'creator': 'AgentTwister Security Testing Platform',
        }

        return story, pdf_metadata, embedded_payloads, techniques_used

    def _embed_payload_pdf(
        self,
        story: List,
        styles: Any,
        payload: str,
        technique: str,
        config: Dict[str, Any]
    ) -> None:
        """Embed a payload using the specified stealth technique in PDF."""
        from reportlab.lib.colors import white, black, Color
        from reportlab.platypus import Paragraph, Spacer, Table
        from reportlab.lib.styles import ParagraphStyle

        if technique == "font_color_match":
            self._embed_font_color_match_pdf(story, payload, config)

        elif technique == "white_on_white":
            self._embed_white_on_white_pdf(story, payload, config)

        elif technique == "tiny_font":
            self._embed_tiny_font_pdf(story, payload, config)

        elif technique == "zero_width_unicode":
            self._embed_zero_width_unicode_pdf(story, payload, config)

        elif technique == "hidden_text_property":
            self._embed_hidden_property_pdf(story, payload, config)

        elif technique == "metadata_injection":
            # This is handled separately in _build_pdf_content
            pass

        elif technique == "hidden_layer":
            self._embed_hidden_layer_pdf(story, payload, config)

        elif technique == "annotation_hidden":
            self._embed_annotation_pdf(story, payload, config)

        elif technique == "invisible_form_field":
            self._embed_invisible_form_field_pdf(story, payload, config)

        elif technique == "header_footer_hidden":
            self._embed_header_footer_pdf(story, payload, config)

        elif technique == "invisible_table":
            self._embed_invisible_table_pdf(story, payload, config)

        elif technique == "overlay_text":
            self._embed_overlay_text_pdf(story, payload, config)

    def _embed_font_color_match_pdf(
        self,
        story: List,
        payload: str,
        config: Dict[str, Any]
    ) -> None:
        """Embed payload with font color matching background (white on white)."""
        from reportlab.lib.colors import Color
        from reportlab.platypus import Paragraph
        from reportlab.lib.styles import ParagraphStyle

        font_color_rgb = config.get("font_color", [255, 255, 255])
        if isinstance(font_color_rgb, str):
            font_color_rgb = [int(font_color_rgb[i:i+2], 16) for i in (0, 2, 4)]

        r, g, b = font_color_rgb[0]/255, font_color_rgb[1]/255, font_color_rgb[2]/255

        hidden_style = ParagraphStyle(
            'FontColorMatch',
            fontSize=10,
            textColor=Color(r, g, b),
        )

        story.append(Paragraph(payload, hidden_style))

    def _embed_white_on_white_pdf(
        self,
        story: List,
        payload: str,
        config: Dict[str, Any]
    ) -> None:
        """Embed payload as white text on white background."""
        from reportlab.lib.colors import white
        from reportlab.platypus import Paragraph
        from reportlab.lib.styles import ParagraphStyle

        hidden_style = ParagraphStyle(
            'WhiteOnWhite',
            fontSize=10,
            textColor=white,
        )

        story.append(Paragraph(payload, hidden_style))

    def _embed_tiny_font_pdf(
        self,
        story: List,
        payload: str,
        config: Dict[str, Any]
    ) -> None:
        """Embed payload with tiny font size (1pt)."""
        from reportlab.lib.colors import white
        from reportlab.platypus import Paragraph
        from reportlab.lib.styles import ParagraphStyle

        font_size = config.get("font_size", 1)
        also_hide = config.get("also_hide_color", True)

        tiny_style = ParagraphStyle(
            'TinyFont',
            fontSize=font_size,
            leading=font_size,
            textColor=white if also_hide else black,
        )

        story.append(Paragraph(payload, tiny_style))

    def _embed_zero_width_unicode_pdf(
        self,
        story: List,
        payload: str,
        config: Dict[str, Any]
    ) -> None:
        """Embed payload using zero-width Unicode characters."""
        zero_chars = config.get(
            "zero_width_chars",
            ["\u200B", "\u200C"]  # zero-width space, zero-width non-joiner
        )

        encoded = self._encode_as_zero_width(payload, zero_chars)

        # Insert at the beginning of the story
        if story:
            first_item = story[0]
            if hasattr(first_item, 'text'):
                first_item.text = encoded + first_item.text
            else:
                story.insert(0, Paragraph(encoded, story[0].style))
        else:
            from reportlab.platypus import Paragraph
            from reportlab.lib.styles import getSampleStyleSheet
            styles = getSampleStyleSheet()
            story.append(Paragraph(encoded, styles['Normal']))

    def _encode_as_zero_width(self, text: str, zero_chars: List[str]) -> str:
        """Encode text as zero-width characters."""
        if len(zero_chars) < 2:
            zero_chars = ["\u200B", "\u200C"]

        zero_0 = zero_chars[0]
        zero_1 = zero_chars[1]

        binary_str = "".join(format(ord(c), '016b') for c in text)
        encoded = ""

        for bit in binary_str:
            if bit == '0':
                encoded += zero_0
            else:
                encoded += zero_1

        return encoded

    def _embed_hidden_property_pdf(
        self,
        story: List,
        payload: str,
        config: Dict[str, Any]
    ) -> None:
        """Embed payload using invisible text (white on white)."""
        self._embed_white_on_white_pdf(story, payload, config)

    def _embed_hidden_layer_pdf(
        self,
        story: List,
        payload: str,
        config: Dict[str, Any]
    ) -> None:
        """Embed payload in a hidden PDF layer."""
        # For basic implementation, use white text
        # Full implementation would use Optional Content Groups
        self._embed_white_on_white_pdf(story, payload, config)

    def _embed_annotation_pdf(
        self,
        story: List,
        payload: str,
        config: Dict[str, Any]
    ) -> None:
        """Embed payload as a hidden annotation."""
        # Store for later rendering in on_first_page/on_later_pages
        if not hasattr(self, '_annotations'):
            self._annotations = []
        self._annotations.append(payload)

    def _embed_invisible_form_field_pdf(
        self,
        story: List,
        payload: str,
        config: Dict[str, Any]
    ) -> None:
        """Embed payload in an invisible form field."""
        # Store for later rendering
        if not hasattr(self, '_form_fields'):
            self._form_fields = []
        self._form_fields.append(payload)

    def _embed_header_footer_pdf(
        self,
        story: List,
        payload: str,
        config: Dict[str, Any]
    ) -> None:
        """Embed payload in footer."""
        if not hasattr(self, '_footer_text'):
            self._footer_text = []
        self._footer_text.append(payload)

    def _embed_invisible_table_pdf(
        self,
        story: List,
        payload: str,
        config: Dict[str, Any]
    ) -> None:
        """Embed payload in an invisible table."""
        from reportlab.lib.colors import white
        from reportlab.platypus import Table, TableStyle
        from reportlab.lib import colors

        # Create a single-cell table with white text and no borders
        table_data = [[payload]]
        table = Table(table_data)

        table.setStyle(TableStyle([
            ('TEXTCOLOR', (0, 0), (-1, -1), white),
            ('BACKGROUND', (0, 0), (-1, -1), white),
            ('BORDER', (0, 0), (-1, -1), 0, white),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTSIZE', (0, 0), (-1, -1), 1),
        ]))

        story.append(table)

    def _embed_overlay_text_pdf(
        self,
        story: List,
        payload: str,
        config: Dict[str, Any]
    ) -> None:
        """Embed payload as overlay text (hidden)."""
        self._embed_tiny_font_pdf(story, payload, {"also_hide_color": True})

    def _on_first_page(self, canvas, doc):
        """Called on first page - add annotations and footer text."""
        from reportlab.lib.colors import white

        # Add annotations if any
        if hasattr(self, '_annotations') and self._annotations:
            canvas.saveState()
            canvas.setFillColor(white)
            canvas.setFont('Helvetica', 1)
            y_pos = 50
            for ann in self._annotations:
                canvas.drawString(10, y_pos, ann)
                y_pos -= 5
            canvas.restoreState()

        # Add footer text if any
        if hasattr(self, '_footer_text') and self._footer_text:
            canvas.saveState()
            canvas.setFillColor(white)
            canvas.setFont('Helvetica', 1)
            y_pos = 30
            for text in self._footer_text:
                canvas.drawString(10, y_pos, text)
                y_pos -= 5
            canvas.restoreState()

    def _on_later_pages(self, canvas, doc):
        """Called on later pages - add footer text."""
        if hasattr(self, '_footer_text') and self._footer_text:
            from reportlab.lib.colors import white
            canvas.saveState()
            canvas.setFillColor(white)
            canvas.setFont('Helvetica', 1)
            y_pos = 30
            for text in self._footer_text:
                canvas.drawString(10, y_pos, text)
                y_pos -= 5
            canvas.restoreState()

    def _generate_dual_view(
        self,
        visible_content: str,
        embedded_payloads: List[str]
    ) -> Dict[str, Any]:
        """Generate dual-view preview data."""
        # Human-visible view (what humans see)
        human_visible = self._create_visible_view(visible_content)

        # LLM-parsed view (what LLMs extract)
        llm_parsed = self._create_parsed_view(visible_content, embedded_payloads)

        return {
            "human_visible_preview": human_visible,
            "llm_parsed_preview": llm_parsed,
            "extracted_payloads": embedded_payloads,
        }

    def _create_visible_view(self, content: str) -> str:
        """Create the human-visible view of content."""
        # Return clean content without embedded payloads
        lines = content.split('\n')
        return '\n'.join(line for line in lines if line.strip())

    def _create_parsed_view(
        self,
        visible_content: str,
        embedded_payloads: List[str]
    ) -> str:
        """Create the LLM-parsed view showing all extracted content."""
        # Simulate what an LLM would parse
        result = visible_content + "\n\n"

        if embedded_payloads:
            result += "[EMBEDDED CONTENT EXTRACTED]\n"
            for i, payload in enumerate(embedded_payloads, 1):
                result += f"- Payload {i}: {payload}\n"

        return result


# Update ToolFactory to include PDFGeneratorTool
def register_pdf_generator_tool() -> None:
    """Register the PDFGeneratorTool with the ToolFactory."""
    from . import ToolFactory
    if "pdf_generator" not in ToolFactory._instances:
        ToolFactory._instances["pdf_generator"] = PDFGeneratorTool()


# Auto-register on import
try:
    register_pdf_generator_tool()
except Exception:
    pass  # May fail if imported during initial module load
