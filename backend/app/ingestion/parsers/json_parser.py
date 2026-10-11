# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence

import json
from typing import BinaryIO

from app.ingestion.parsers._structured_data import elements_from_data
from app.ingestion.parsers.base import ParsedElement, Parser


class JsonParser(Parser):
    def extract_elements(self, file: BinaryIO) -> list[ParsedElement]:
        data = json.loads(file.read().decode("utf-8", errors="replace"))
        return elements_from_data(data)
