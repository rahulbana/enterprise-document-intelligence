# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Default strategy, unchanged from Phase 10: word-packing per element,
# blind to what kind of content the element holds (prose, table row, ...).
# Cheap and predictable; the tradeoff is that a large table/sheet element
# can get cut mid-row purely on character count. Use "structure_aware" if
# that tradeoff bites — see structure_aware.py.

from typing import Any

from app.ingestion.chunking.base import ChunkingStrategy
from app.ingestion.chunking.word_packing import chunk_text
from app.ingestion.parsers.base import ParsedElement


class FixedSizeChunkingStrategy(ChunkingStrategy):
    def chunk(
        self, elements: list[ParsedElement], *, chunk_size: int, chunk_overlap: int
    ) -> list[tuple[str, dict[str, Any]]]:
        result: list[tuple[str, dict[str, Any]]] = []
        for element in elements:
            chunks = chunk_text(element.content, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
            for chunk in chunks:
                result.append((chunk, element.metadata))
        return result
