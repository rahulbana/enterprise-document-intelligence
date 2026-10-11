# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence

from app.ingestion.chunking import chunk_text


def test_empty_text_returns_no_chunks() -> None:
    assert chunk_text("", chunk_size=100, chunk_overlap=10) == []
    assert chunk_text("   ", chunk_size=100, chunk_overlap=10) == []


def test_short_text_returns_single_chunk() -> None:
    chunks = chunk_text("hello world", chunk_size=100, chunk_overlap=10)

    assert chunks == ["hello world"]


def test_never_splits_a_word() -> None:
    text = " ".join(f"word{i}" for i in range(500))

    chunks = chunk_text(text, chunk_size=50, chunk_overlap=10)

    all_words = set(text.split())
    for chunk in chunks:
        for word in chunk.split():
            assert word in all_words


def test_chunks_respect_size_budget() -> None:
    text = " ".join(f"word{i}" for i in range(500))

    chunks = chunk_text(text, chunk_size=50, chunk_overlap=10)

    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 50 or len(chunk.split()) == 1


def test_single_word_longer_than_chunk_size_is_kept_whole() -> None:
    long_word = "x" * 200

    chunks = chunk_text(long_word, chunk_size=50, chunk_overlap=10)

    assert chunks == [long_word]


def test_consecutive_chunks_overlap() -> None:
    text = " ".join(f"word{i}" for i in range(100))

    chunks = chunk_text(text, chunk_size=60, chunk_overlap=20)

    assert len(chunks) > 1
    first_words = chunks[0].split()
    second_words = chunks[1].split()
    assert set(first_words) & set(second_words), "consecutive chunks should share some words"


def test_zero_overlap_produces_no_shared_words() -> None:
    text = " ".join(f"word{i}" for i in range(100))

    chunks = chunk_text(text, chunk_size=60, chunk_overlap=0)

    assert len(chunks) > 1
    for first, second in zip(chunks, chunks[1:], strict=False):
        assert not (set(first.split()) & set(second.split()))


def test_all_words_are_covered_by_some_chunk() -> None:
    words = [f"word{i}" for i in range(200)]
    text = " ".join(words)

    chunks = chunk_text(text, chunk_size=80, chunk_overlap=15)

    covered = set()
    for chunk in chunks:
        covered.update(chunk.split())
    assert covered == set(words)


def test_progress_is_always_made_even_with_large_overlap() -> None:
    # chunk_overlap >= chunk_size would loop forever without the forward-
    # progress guard; this must still terminate and make progress.
    text = " ".join(f"word{i}" for i in range(50))

    chunks = chunk_text(text, chunk_size=20, chunk_overlap=1000)

    assert len(chunks) > 1
