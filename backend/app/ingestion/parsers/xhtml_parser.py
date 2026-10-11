# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# XHTML is the same markup as HTML, just served/saved with stricter
# well-formedness — same parsing logic as HtmlParser.

from typing import BinaryIO

from app.ingestion.parsers._html_common import elements_from_html
from app.ingestion.parsers.base import ParsedElement, Parser


class XhtmlParser(Parser):
    def extract_elements(self, file: BinaryIO) -> list[ParsedElement]:
        html = file.read().decode("utf-8", errors="replace")
        return elements_from_html(html)
