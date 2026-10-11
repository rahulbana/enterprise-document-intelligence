# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# One JSON object per line — one element per line, not per key, since each
# line is already an independent record (that's the point of JSONL).

import json
from typing import BinaryIO

from app.ingestion.parsers._structured_data import render_value
from app.ingestion.parsers.base import ParsedElement, Parser


class JsonlParser(Parser):
    def extract_elements(self, file: BinaryIO) -> list[ParsedElement]:
        text = file.read().decode("utf-8", errors="replace")
        elements = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            data = json.loads(line)
            elements.append(
                ParsedElement(content=render_value(data), metadata={"line": line_number})
            )
        return elements
