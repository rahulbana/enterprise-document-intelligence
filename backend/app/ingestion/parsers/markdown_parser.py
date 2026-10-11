# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Markdown is ingested as plain text (formatting left in) — good enough for
# chunking/embedding. A dedicated formatting-stripping pass can replace this
# later without touching any other parser.

from typing import BinaryIO

from app.ingestion.parsers.base import ParsedElement, Parser


class MarkdownParser(Parser):
    def extract_elements(self, file: BinaryIO) -> list[ParsedElement]:
        text = file.read().decode("utf-8", errors="replace")
        return [ParsedElement(content=text)]
