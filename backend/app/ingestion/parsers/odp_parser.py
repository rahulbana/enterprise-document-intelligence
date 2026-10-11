# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# One "body" element per slide (all its shape text, tables aren't broken out
# separately the way PptxParser's are — ODF's table model inside a
# presentation is uncommon enough that the added complexity isn't worth it
# here) plus a separate "notes" element when the slide has speaker notes.
# Less granular than the PPTX parser (no per-shape/hyperlink/image
# breakdown) — a reasonable scope reduction for a much less common format.

from typing import BinaryIO

from odf import teletype
from odf.draw import Page
from odf.opendocument import load
from odf.presentation import Notes

from app.ingestion.parsers.base import ParsedElement, Parser


class OdpParser(Parser):
    def extract_elements(self, file: BinaryIO) -> list[ParsedElement]:
        document = load(file)

        elements: list[ParsedElement] = []
        for slide_index, page in enumerate(document.presentation.getElementsByType(Page)):
            slide_number = slide_index + 1
            notes_elements = page.getElementsByType(Notes)

            body_text = "".join(
                teletype.extractText(child)
                for child in page.childNodes
                if getattr(child, "tagName", "") != "presentation:notes"
            ).strip()
            if body_text:
                body_metadata = {"slide": slide_number, "kind": "body"}
                elements.append(ParsedElement(content=body_text, metadata=body_metadata))

            for notes in notes_elements:
                notes_text = teletype.extractText(notes).strip()
                if notes_text:
                    elements.append(
                        ParsedElement(
                            content=notes_text, metadata={"slide": slide_number, "kind": "notes"}
                        )
                    )

        return elements
