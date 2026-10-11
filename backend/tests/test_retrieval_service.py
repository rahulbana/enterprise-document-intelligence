# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Unit tests for the retrieval pipeline: real DB session (for RBAC-relevant
# user/department rows), fake embedding provider/vector store/reranker — no
# network, no live Weaviate or cross-encoder needed.

from app.models.user import UserRole
from app.repositories import department_repository, user_repository
from app.services.retrieval_service import retrieve_chunks
from tests.fakes import FakeEmbeddingProvider, FakeReranker, FakeVectorRepository


def _create_user(db_session, email: str):
    return user_repository.create(
        db_session, email=email, hashed_password="hashed", full_name="Test", role=UserRole.USER
    )


def test_retrieve_chunks_scopes_to_owner(db_session) -> None:
    owner = _create_user(db_session, "owner@example.com")
    other = _create_user(db_session, "other@example.com")

    vector_repository = FakeVectorRepository()
    vector_repository.replace_document_chunks(
        document_id=1,
        document_version_id=1,
        owner_id=owner.id,
        department_ids=[],
        chunks=["the quick brown fox"],
        vectors=[[0.1]],
        metadatas=[{}],
    )

    results = retrieve_chunks(
        current_user=other,
        query="quick fox",
        embedding_provider=FakeEmbeddingProvider(),
        vector_repository=vector_repository,
        reranker=FakeReranker(),
    )

    assert results == []


def test_retrieve_chunks_returns_owners_own_chunks(db_session) -> None:
    owner = _create_user(db_session, "owner2@example.com")

    vector_repository = FakeVectorRepository()
    vector_repository.replace_document_chunks(
        document_id=1,
        document_version_id=1,
        owner_id=owner.id,
        department_ids=[],
        chunks=["the quick brown fox"],
        vectors=[[0.1]],
        metadatas=[{}],
    )

    results = retrieve_chunks(
        current_user=owner,
        query="quick fox",
        embedding_provider=FakeEmbeddingProvider(),
        vector_repository=vector_repository,
        reranker=FakeReranker(),
    )

    assert len(results) == 1
    assert results[0].document_id == 1
    assert results[0].content == "the quick brown fox"


def test_retrieve_chunks_includes_department_docs_for_members(db_session) -> None:
    admin = _create_user(db_session, "admin@example.com")
    member = _create_user(db_session, "member@example.com")
    department = department_repository.create(db_session, name="Engineering", description=None)
    user_repository.set_departments(db_session, member, [department])

    vector_repository = FakeVectorRepository()
    vector_repository.replace_document_chunks(
        document_id=2,
        document_version_id=2,
        owner_id=admin.id,
        department_ids=[department.id],
        chunks=["department handbook content"],
        vectors=[[0.1]],
        metadatas=[{}],
    )

    results = retrieve_chunks(
        current_user=member,
        query="handbook content",
        embedding_provider=FakeEmbeddingProvider(),
        vector_repository=vector_repository,
        reranker=FakeReranker(),
    )

    assert len(results) == 1
    assert results[0].document_id == 2


def test_retrieve_chunks_respects_top_k(db_session) -> None:
    owner = _create_user(db_session, "owner3@example.com")

    vector_repository = FakeVectorRepository()
    vector_repository.replace_document_chunks(
        document_id=3,
        document_version_id=3,
        owner_id=owner.id,
        department_ids=[],
        chunks=["alpha content one", "alpha content two", "alpha content three"],
        vectors=[[0.1], [0.2], [0.3]],
        metadatas=[{}, {}, {}],
    )

    results = retrieve_chunks(
        current_user=owner,
        query="alpha content",
        embedding_provider=FakeEmbeddingProvider(),
        vector_repository=vector_repository,
        reranker=FakeReranker(),
        top_k=2,
    )

    assert len(results) == 2


def test_retrieve_chunks_carries_hybrid_and_rerank_scores(db_session) -> None:
    owner = _create_user(db_session, "owner4@example.com")

    vector_repository = FakeVectorRepository()
    vector_repository.replace_document_chunks(
        document_id=4,
        document_version_id=4,
        owner_id=owner.id,
        department_ids=[],
        chunks=["matches query exactly"],
        vectors=[[0.1]],
        metadatas=[{}],
    )

    results = retrieve_chunks(
        current_user=owner,
        query="matches query exactly",
        embedding_provider=FakeEmbeddingProvider(),
        vector_repository=vector_repository,
        reranker=FakeReranker(),
    )

    assert len(results) == 1
    assert results[0].hybrid_score == 3.0  # all 3 query words overlap
    assert results[0].rerank_score == 1.0  # sole candidate, FakeReranker: count - 0


def test_retrieve_chunks_logs_per_stage_timing(db_session, caplog) -> None:
    import logging

    owner = _create_user(db_session, "owner5@example.com")
    vector_repository = FakeVectorRepository()
    vector_repository.replace_document_chunks(
        document_id=5,
        document_version_id=5,
        owner_id=owner.id,
        department_ids=[],
        chunks=["timed retrieval stage"],
        vectors=[[0.1]],
        metadatas=[{}],
    )

    with caplog.at_level(logging.DEBUG, logger="app.services.retrieval_service"):
        retrieve_chunks(
            current_user=owner,
            query="timed retrieval stage",
            embedding_provider=FakeEmbeddingProvider(),
            vector_repository=vector_repository,
            reranker=FakeReranker(),
        )

    messages = [r.message for r in caplog.records]
    assert any("embed_query took" in m for m in messages)
    assert any("hybrid_search took" in m and "1 candidates" in m for m in messages)
    assert any("rerank took" in m for m in messages)
