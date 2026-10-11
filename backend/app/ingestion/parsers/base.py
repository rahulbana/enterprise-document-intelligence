# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Parser interface: turns a raw file into structured elements for chunking/
# embedding. One element per structural unit the format actually has (a PDF
# page, a PPTX slide/notes-block/table, an XLSX sheet/table, an email's
# header vs. body, ...); a plain-text format just yields a single element
# with empty metadata. Every chunking strategy (app/ingestion/chunking/)
# operates per-element, so a chunk never straddles an element boundary
# regardless of which one is configured, and every chunk carries its source
# element's metadata — that's what lets a citation eventually say "slide 3"
# or "Sheet1 rows 12-18" instead of just "this document".

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, BinaryIO


@dataclass(frozen=True)
class ParsedElement:
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


class Parser(ABC):
    @abstractmethod
    def extract_elements(self, file: BinaryIO) -> list[ParsedElement]: ...
