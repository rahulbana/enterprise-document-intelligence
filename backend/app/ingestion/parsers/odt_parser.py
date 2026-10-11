# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Walks paragraphs/headings in document order (odfpy doesn't group them for
# you) and sections content under whichever heading precedes it — same
# approach as the HTML parsers' heading-sectioning, adapted to ODF's element
# model.

from typing import BinaryIO

from odf import teletype
from odf.opendocument import load

from app.ingestion.parsers.base import ParsedElement, Parser


class OdtParser(Parser):
    def extract_elements(self, file: BinaryIO) -> list[ParsedElement]:
        document = load(file)

        elements: list[ParsedElement] = []
        current_heading: str | None = None
        current_level: int | None = None
        buffer: list[str] = []

        def flush() -> None:
            content = "\n".join(buffer).strip()
            if content:
                metadata = {"heading": current_heading, "level": current_level}
                elements.append(ParsedElement(content=content, metadata=metadata))
            buffer.clear()

        for child in document.text.childNodes:
            text = teletype.extractText(child).strip()
            if not text:
                continue
            if getattr(child, "tagName", "") == "text:h":
                flush()
                current_heading = text
                level = child.getAttribute("outlinelevel")
                current_level = int(level) if level else None
                buffer.append(text)
            else:
                buffer.append(text)

        flush()
        return elements
