# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana

from typing import BinaryIO

from app.ingestion.parsers._html_common import elements_from_html
from app.ingestion.parsers.base import ParsedElement, Parser


class HtmlParser(Parser):
    def extract_elements(self, file: BinaryIO) -> list[ParsedElement]:
        html = file.read().decode("utf-8", errors="replace")
        return elements_from_html(html)
