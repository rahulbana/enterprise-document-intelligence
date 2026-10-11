# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# One element per spine document (chapter), each run through the same
# heading-sectioning HTML logic as HtmlParser since EPUB chapters are just
# XHTML. ebooklib's read_epub wants a real file path, not a stream, so the
# uploaded bytes are written to a temp file for the duration of the parse.

import tempfile
from pathlib import Path
from typing import BinaryIO

import ebooklib
from ebooklib import epub

from app.ingestion.parsers._html_common import elements_from_html
from app.ingestion.parsers.base import ParsedElement, Parser


class EpubParser(Parser):
    def extract_elements(self, file: BinaryIO) -> list[ParsedElement]:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / "book.epub"
            tmp_path.write_bytes(file.read())
            book = epub.read_epub(str(tmp_path), options={"ignore_ncx": True})

            elements: list[ParsedElement] = []
            for chapter_index, item in enumerate(book.get_items_of_type(ebooklib.ITEM_DOCUMENT)):
                html = item.get_content().decode("utf-8", errors="replace")
                for element in elements_from_html(html):
                    metadata = {"chapter_index": chapter_index, "chapter_name": item.get_name()}
                    metadata.update(element.metadata)
                    elements.append(ParsedElement(content=element.content, metadata=metadata))
            return elements
