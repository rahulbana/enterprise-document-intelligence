# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# PDF parsing via pdfplumber: real per-page prose text plus real table
# structure (row/column-aware, not linearized like plain text extraction
# would leave it) — pdfplumber's geometric table detection, no ML/torch
# involved (deliberately not Docling — see PLAN.md Phase 10 for why).
# Pages with near-no extractable text (scanned/image-only) fall back to OCR
# for that page only (pdf2image renders just that page, pytesseract reads
# it), so a mostly-text PDF with a few scanned pages doesn't pay to
# rasterize every page.

import io
from typing import BinaryIO

import pdfplumber
import pytesseract
from pdf2image import convert_from_bytes

from app.ingestion.parsers.base import ParsedElement, Parser

# A page with fewer extracted characters than this is treated as scanned/
# image-only (real body text easily clears this; a mostly-blank or
# image-only page won't).
_MIN_CHARS_BEFORE_OCR_FALLBACK = 20


class PdfParser(Parser):
    def extract_elements(self, file: BinaryIO) -> list[ParsedElement]:
        data = file.read()
        elements: list[ParsedElement] = []

        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for index, page in enumerate(pdf.pages):
                page_number = index + 1
                text = (page.extract_text() or "").strip()
                if len(text) < _MIN_CHARS_BEFORE_OCR_FALLBACK:
                    text = self._ocr_page(data, page_number=page_number)
                if text:
                    elements.append(
                        ParsedElement(content=text, metadata={"page": page_number, "kind": "text"})
                    )

                for table_index, table in enumerate(page.extract_tables()):
                    rows = [" | ".join(cell or "" for cell in row) for row in table]
                    content = "\n".join(row for row in rows if row.strip())
                    if content:
                        elements.append(
                            ParsedElement(
                                content=content,
                                metadata={
                                    "page": page_number,
                                    "kind": "table",
                                    "table_index": table_index,
                                },
                            )
                        )

        return elements

    def _ocr_page(self, pdf_bytes: bytes, *, page_number: int) -> str:
        images = convert_from_bytes(pdf_bytes, first_page=page_number, last_page=page_number)
        if not images:
            return ""
        return pytesseract.image_to_string(images[0]).strip()
