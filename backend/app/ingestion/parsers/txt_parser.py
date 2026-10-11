# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana

from typing import BinaryIO

from app.ingestion.parsers.base import ParsedElement, Parser


class TxtParser(Parser):
    def extract_elements(self, file: BinaryIO) -> list[ParsedElement]:
        text = file.read().decode("utf-8", errors="replace")
        return [ParsedElement(content=text)]
