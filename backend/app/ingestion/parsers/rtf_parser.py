# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana

from typing import BinaryIO

from striprtf.striprtf import rtf_to_text

from app.ingestion.parsers.base import ParsedElement, Parser


class RtfParser(Parser):
    def extract_elements(self, file: BinaryIO) -> list[ParsedElement]:
        raw = file.read().decode("utf-8", errors="replace")
        text = rtf_to_text(raw).strip()
        return [ParsedElement(content=text)] if text else []
