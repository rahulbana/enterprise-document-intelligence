# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence

from typing import BinaryIO

import yaml

from app.ingestion.parsers._structured_data import elements_from_data
from app.ingestion.parsers.base import ParsedElement, Parser


class YamlParser(Parser):
    def extract_elements(self, file: BinaryIO) -> list[ParsedElement]:
        data = yaml.safe_load(file.read().decode("utf-8", errors="replace"))
        return elements_from_data(data) if data is not None else []
