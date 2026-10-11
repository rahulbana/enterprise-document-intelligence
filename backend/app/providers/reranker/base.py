# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Reranker interface. Takes a query plus the candidate documents from hybrid
# search and returns them reordered best-first — a cross-encoder scores the
# (query, document) pair directly, which is more accurate than the bi-encoder
# similarity hybrid search already used to pick candidates, at the cost of
# being too slow to run over the whole corpus (hence: rerank a small
# candidate set, not everything).

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class RankedIndex:
    index: int
    score: float


class Reranker(ABC):
    @abstractmethod
    def rerank(self, query: str, documents: list[str]) -> list[RankedIndex]:
        """Return every input index paired with its reranker score, sorted
        best-first (highest score first)."""
        ...
