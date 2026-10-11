# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Content-aware / document-structure-based chunking: routes each element by
# its parser-assigned metadata["kind"] instead of treating every element's
# text the same way.
#
# Tabular elements (XLSX/ODS/CSV/TSV sheets, PDF/DOCX/PPTX tables) are
# rendered by their parsers as one line per row (e.g. "Row 2 (A2:B2):
# Item=Widgets, Quantity=10" — see xlsx_parser.py), with the header already
# folded into every line. fixed_size/recursive both chunk by character count
# and don't know a newline is a row boundary, so a large table can get cut
# mid-row. This strategy packs whole lines instead, so a chunk boundary
# only ever falls between rows, never inside one.
#
# Everything else (prose: PDF/DOCX body text, PPTX titles/notes/textboxes,
# email header/body, ...) is prose, not rows — delegated to
# RecursiveChunkingStrategy for the same paragraph/sentence-aware splitting
# "recursive" gives you directly.

from typing import Any

from app.ingestion.chunking.base import ChunkingStrategy
from app.ingestion.chunking.recursive import RecursiveChunkingStrategy
from app.ingestion.parsers.base import ParsedElement

# CSV/TSV elements carry no "kind" key at all (see csv_parser.py) but are
# always one-row-per-line by construction, so a missing kind is treated as
# tabular too rather than silently falling back to prose splitting.
_TABULAR_KINDS = {"table", "sheet"}
_KNOWN_PROSE_KINDS = {"text", "body", "header", "footer", "title", "textbox", "notes"}


def _is_tabular(element: ParsedElement) -> bool:
    kind = element.metadata.get("kind")
    if kind in _TABULAR_KINDS:
        return True
    return kind is None and "headers" in element.metadata


def _pack_lines(lines: list[str], chunk_size: int) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for line in lines:
        added = len(line) + (1 if current else 0)
        if current and current_len + added > chunk_size:
            chunks.append("\n".join(current))
            # Each row line already carries its own header labels (see
            # xlsx_parser.py's "Header=Value" rendering), so unlike prose
            # there's no context lost by starting the next chunk cleanly —
            # one line of trailing overlap is enough to signal continuity.
            current = [current[-1]]
            current_len = len(current[0])
        current.append(line)
        current_len += added
    if current:
        chunks.append("\n".join(current))
    return chunks


class StructureAwareChunkingStrategy(ChunkingStrategy):
    def __init__(self) -> None:
        self._prose_strategy = RecursiveChunkingStrategy()

    def chunk(
        self, elements: list[ParsedElement], *, chunk_size: int, chunk_overlap: int
    ) -> list[tuple[str, dict[str, Any]]]:
        # Dispatched per element (not batched into two passes) so the
        # output preserves the document's original element order — a
        # prose-then-table-then-prose document shouldn't come back with
        # every table's chunks reordered to the end.
        result: list[tuple[str, dict[str, Any]]] = []
        for element in elements:
            if _is_tabular(element):
                lines = [line for line in element.content.splitlines() if line.strip()]
                for chunk in _pack_lines(lines, chunk_size):
                    result.append((chunk, element.metadata))
            else:
                result.extend(
                    self._prose_strategy.chunk(
                        [element], chunk_size=chunk_size, chunk_overlap=chunk_overlap
                    )
                )
        return result
