# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# ChunkingStrategy interface: turns a document's parsed elements into
# (chunk_text, chunk_metadata) pairs ready for embedding. Every strategy
# operates per-ParsedElement, not on one big joined string, so a chunk never
# straddles a structural boundary (a PDF page, a PPTX slide, an XLSX sheet,
# ...) regardless of which strategy is chosen.

from abc import ABC, abstractmethod
from typing import Any

from app.ingestion.parsers.base import ParsedElement


class ChunkingStrategy(ABC):
    @abstractmethod
    def chunk(
        self, elements: list[ParsedElement], *, chunk_size: int, chunk_overlap: int
    ) -> list[tuple[str, dict[str, Any]]]: ...
