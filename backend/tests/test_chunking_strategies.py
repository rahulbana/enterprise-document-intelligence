# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Unit tests for the pluggable ChunkingStrategy layer (Phase 11) — the
# factory's dispatch, and each strategy's actual chunk() entry point (the
# thing ingestion_service.py calls), not just the word_packing primitive
# tests/test_chunking.py already covers.

import pytest

from app.ingestion.chunking.factory import get_chunking_strategy
from app.ingestion.chunking.fixed_size import FixedSizeChunkingStrategy
from app.ingestion.chunking.recursive import RecursiveChunkingStrategy
from app.ingestion.chunking.structure_aware import StructureAwareChunkingStrategy
from app.ingestion.parsers.base import ParsedElement


def test_factory_defaults_to_fixed_size(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "CHUNKING_STRATEGY", "fixed_size")
    get_chunking_strategy.cache_clear()

    assert isinstance(get_chunking_strategy(), FixedSizeChunkingStrategy)


def test_factory_raises_for_unknown_strategy(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "CHUNKING_STRATEGY", "bogus")
    get_chunking_strategy.cache_clear()

    with pytest.raises(ValueError, match="Unknown CHUNKING_STRATEGY"):
        get_chunking_strategy()
    get_chunking_strategy.cache_clear()


def test_fixed_size_never_straddles_an_element_boundary() -> None:
    elements = [
        ParsedElement(content="alpha beta gamma", metadata={"page": 1}),
        ParsedElement(content="delta epsilon zeta", metadata={"page": 2}),
    ]

    pairs = FixedSizeChunkingStrategy().chunk(elements, chunk_size=1000, chunk_overlap=0)

    assert [content for content, _ in pairs] == ["alpha beta gamma", "delta epsilon zeta"]
    assert [metadata for _, metadata in pairs] == [{"page": 1}, {"page": 2}]


def test_recursive_prefers_paragraph_boundaries_over_word_count() -> None:
    text = "First paragraph is short.\n\n" + "filler word. " * 20 + "\n\nLast paragraph is short."
    elements = [ParsedElement(content=text, metadata={"kind": "body"})]

    pairs = RecursiveChunkingStrategy().chunk(elements, chunk_size=100, chunk_overlap=20)

    assert len(pairs) > 1
    # First chunk should end at (or very near) the first paragraph break,
    # not mid-sentence purely on character count like fixed_size would.
    assert pairs[0][0].startswith("First paragraph is short.")


def test_recursive_falls_back_to_word_packing_for_one_giant_token() -> None:
    # No paragraph, line, sentence, or word boundary anywhere in this text —
    # every separator in turn fails to shrink it, so it bottoms out at
    # word_packing.chunk_text, which guarantees it never splits a "word"
    # (here, the whole 300-char blob) even when that exceeds chunk_size.
    long_token = "x" * 300
    elements = [ParsedElement(content=long_token, metadata={})]

    pairs = RecursiveChunkingStrategy().chunk(elements, chunk_size=50, chunk_overlap=10)

    assert pairs == [(long_token, {})]


def test_structure_aware_never_splits_a_table_row() -> None:
    rows = "\n".join(f"Row {i} (A{i}:B{i}): Item=Widget{i}, Qty={i}" for i in range(2, 30))
    elements = [ParsedElement(content=f"# Sheet1\n{rows}", metadata={"kind": "sheet"})]

    pairs = StructureAwareChunkingStrategy().chunk(elements, chunk_size=150, chunk_overlap=20)

    assert len(pairs) > 1
    for content, metadata in pairs:
        assert metadata == {"kind": "sheet"}
        for line in content.splitlines():
            assert line.startswith("Row") or line.startswith("#")


def test_structure_aware_routes_csv_style_missing_kind_as_tabular() -> None:
    rows = "\n".join(f"Row {i}: Name=Person{i}, Score={i}" for i in range(2, 20))
    elements = [ParsedElement(content=rows, metadata={"headers": ["Name", "Score"]})]

    pairs = StructureAwareChunkingStrategy().chunk(elements, chunk_size=100, chunk_overlap=10)

    for content, _ in pairs:
        for line in content.splitlines():
            assert line.startswith("Row")


def test_structure_aware_routes_prose_through_recursive() -> None:
    text = "Paragraph one.\n\n" + "word " * 40
    elements = [ParsedElement(content=text, metadata={"kind": "body"})]

    pairs = StructureAwareChunkingStrategy().chunk(elements, chunk_size=60, chunk_overlap=10)

    assert len(pairs) > 1
    assert pairs[0][0].startswith("Paragraph one.")


def test_structure_aware_preserves_element_order_across_mixed_content() -> None:
    elements = [
        ParsedElement(content="Intro prose.", metadata={"kind": "body"}),
        ParsedElement(content="Row 2: A=1\nRow 3: A=2", metadata={"kind": "table"}),
        ParsedElement(content="Outro prose.", metadata={"kind": "body"}),
    ]

    pairs = StructureAwareChunkingStrategy().chunk(elements, chunk_size=1000, chunk_overlap=0)

    kinds = [metadata["kind"] for _, metadata in pairs]
    assert kinds == ["body", "table", "body"]
