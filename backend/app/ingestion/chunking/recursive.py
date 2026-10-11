# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Recursive character-level chunking: splits each element on the first
# separator in _SEPARATORS ("\n\n" paragraph breaks, then "\n" lines, then
# ". " sentence ends, then " " words), recursing into any resulting piece
# still over chunk_size with the next separator down the list. This keeps
# paragraph/sentence boundaries intact wherever the text allows it, instead
# of "fixed_size"'s blind word-count cut — better prose coherence at the
# same chunk_size/overlap budget, at the cost of a slightly less predictable
# chunk count. Falls back to word_packing.chunk_text only for a piece that's
# still too big after every separator (e.g. one absurdly long "word").

from typing import Any

from app.ingestion.chunking.base import ChunkingStrategy
from app.ingestion.chunking.word_packing import chunk_text
from app.ingestion.parsers.base import ParsedElement

_SEPARATORS = ["\n\n", "\n", ". ", " "]


def _split_on(text: str, separator: str) -> list[str]:
    parts = text.split(separator)
    # Keep the separator attached to each piece (except the last) so
    # reassembly during merging doesn't lose the paragraph/sentence break.
    return [p + separator if i < len(parts) - 1 else p for i, p in enumerate(parts)]


def _split_recursively(text: str, chunk_size: int, separators: list[str]) -> list[str]:
    if len(text) <= chunk_size:
        return [text] if text.strip() else []
    if not separators:
        # No separator left to try — hand off to word-packing, the only
        # primitive that's guaranteed to make progress on arbitrary text.
        return chunk_text(text, chunk_size=chunk_size, chunk_overlap=0)

    separator, *rest = separators
    pieces = _split_on(text, separator)
    result: list[str] = []
    for piece in pieces:
        if len(piece) <= chunk_size:
            if piece.strip():
                result.append(piece)
        else:
            result.extend(_split_recursively(piece, chunk_size, rest))
    return result


def _merge_with_overlap(pieces: list[str], chunk_size: int, chunk_overlap: int) -> list[str]:
    if not pieces:
        return []

    chunks: list[str] = []
    current = ""
    for piece in pieces:
        if current and len(current) + len(piece) > chunk_size:
            chunks.append(current.strip())
            overlap_text = current[-chunk_overlap:] if chunk_overlap > 0 else ""
            current = overlap_text + piece
        else:
            current += piece
    if current.strip():
        chunks.append(current.strip())
    return chunks


class RecursiveChunkingStrategy(ChunkingStrategy):
    def chunk(
        self, elements: list[ParsedElement], *, chunk_size: int, chunk_overlap: int
    ) -> list[tuple[str, dict[str, Any]]]:
        result: list[tuple[str, dict[str, Any]]] = []
        for element in elements:
            pieces = _split_recursively(element.content, chunk_size, _SEPARATORS)
            for chunk in _merge_with_overlap(pieces, chunk_size, chunk_overlap):
                result.append((chunk, element.metadata))
        return result
