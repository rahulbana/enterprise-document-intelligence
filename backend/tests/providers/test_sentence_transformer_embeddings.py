# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# The real SentenceTransformer model is never loaded in tests (that would
# download multi-hundred-MB weights); a fake stands in to verify the
# provider's own logic: constructor args, prefixing, and dimension reporting.

import numpy as np
import pytest

from app.core.config import settings
from app.providers.embeddings import sentence_transformer_embeddings as module
from app.providers.embeddings.sentence_transformer_embeddings import (
    SentenceTransformerEmbeddingProvider,
)


class FakeSentenceTransformer:
    def __init__(
        self, model_name: str, device: str, trust_remote_code: bool, local_files_only: bool
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.trust_remote_code = trust_remote_code
        self.local_files_only = local_files_only
        self.encode_calls: list[str | list[str]] = []

    def get_sentence_embedding_dimension(self) -> int:
        return 3

    def encode(self, texts: str | list[str], normalize_embeddings: bool = True) -> np.ndarray:
        self.encode_calls.append(texts)
        if isinstance(texts, str):
            return np.array([1.0, 2.0, 3.0])
        return np.array([[1.0, 2.0, 3.0] for _ in texts])


@pytest.fixture
def fake_model(monkeypatch: pytest.MonkeyPatch) -> FakeSentenceTransformer:
    holder: dict[str, FakeSentenceTransformer] = {}

    def factory(
        model_name: str, device: str, trust_remote_code: bool, local_files_only: bool
    ) -> FakeSentenceTransformer:
        holder["instance"] = FakeSentenceTransformer(
            model_name, device, trust_remote_code, local_files_only
        )
        return holder["instance"]

    monkeypatch.setattr(module, "SentenceTransformer", factory)
    provider = SentenceTransformerEmbeddingProvider()
    fake = holder["instance"]
    fake.provider = provider  # type: ignore[attr-defined]
    return fake


def test_constructs_with_configured_model_and_defaults_no_trust_remote_code(
    fake_model: FakeSentenceTransformer,
) -> None:
    assert fake_model.model_name == settings.SENTENCE_TRANSFORMER_EMBEDDING_MODEL
    assert fake_model.model_name == "sentence-transformers/all-MiniLM-L6-v2"
    assert fake_model.trust_remote_code is False
    assert fake_model.local_files_only == settings.SENTENCE_TRANSFORMER_LOCAL_FILES_ONLY


def test_embed_documents_defaults_to_no_prefix(fake_model: FakeSentenceTransformer) -> None:
    result = fake_model.provider.embed_documents(["hello"])  # type: ignore[attr-defined]

    assert fake_model.encode_calls[-1] == ["hello"]
    assert result == [[1.0, 2.0, 3.0]]


def test_embed_query_defaults_to_no_prefix(fake_model: FakeSentenceTransformer) -> None:
    result = fake_model.provider.embed_query("hello")  # type: ignore[attr-defined]

    assert fake_model.encode_calls[-1] == "hello"
    assert result == [1.0, 2.0, 3.0]


def test_prefixes_are_applied_when_configured(
    fake_model: FakeSentenceTransformer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "SENTENCE_TRANSFORMER_QUERY_PREFIX", "search_query: ")
    monkeypatch.setattr(settings, "SENTENCE_TRANSFORMER_DOCUMENT_PREFIX", "search_document: ")

    fake_model.provider.embed_documents(["hello"])  # type: ignore[attr-defined]
    fake_model.provider.embed_query("hello")  # type: ignore[attr-defined]

    assert fake_model.encode_calls == [["search_document: hello"], "search_query: hello"]


def test_dimensions_reads_from_model(fake_model: FakeSentenceTransformer) -> None:
    assert fake_model.provider.dimensions == 3  # type: ignore[attr-defined]
