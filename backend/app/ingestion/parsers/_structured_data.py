# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Shared "turn a parsed JSON/YAML object into elements" logic — a leading
# underscore since this isn't itself a registered Parser, just a helper the
# JSON and YAML parsers both call. A top-level list becomes one element per
# item (metadata: index); a top-level dict becomes one element per key
# (metadata: key); anything else (a bare scalar) becomes a single element.

import json
from typing import Any

from app.ingestion.parsers.base import ParsedElement


def render_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, indent=2, default=str, ensure_ascii=False)


def elements_from_data(data: Any) -> list[ParsedElement]:
    if isinstance(data, list):
        return [
            ParsedElement(content=render_value(item), metadata={"index": index})
            for index, item in enumerate(data)
        ]
    if isinstance(data, dict):
        return [
            ParsedElement(content=render_value(value), metadata={"key": str(key)})
            for key, value in data.items()
        ]
    return [ParsedElement(content=render_value(data))]
