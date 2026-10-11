# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Word-based chunking with overlap: packs whole words into ~chunk_size
# character budgets (never splits a word mid-token) and carries roughly
# chunk_overlap characters' worth of trailing words into the next chunk for
# context continuity across chunk boundaries. The primitive behind the
# "fixed_size" strategy, and reused by "recursive" as its final fallback
# once a segment has been split down to nothing smaller than a word.


def chunk_text(text: str, *, chunk_size: int, chunk_overlap: int) -> list[str]:
    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = start
        length = 0
        while end < len(words):
            added = len(words[end]) + (1 if end > start else 0)
            if length + added > chunk_size and end > start:
                break
            length += added
            end += 1

        chunks.append(" ".join(words[start:end]))
        if end >= len(words):
            break

        # Walk backward from the chunk's end to find how many trailing words
        # fit within chunk_overlap characters, and resume the next chunk there.
        overlap_start = end
        overlap_length = 0
        while overlap_start > start:
            candidate = len(words[overlap_start - 1]) + 1
            if overlap_length + candidate > chunk_overlap:
                break
            overlap_length += candidate
            overlap_start -= 1

        start = overlap_start if overlap_start > start else end

    return chunks
