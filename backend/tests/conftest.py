# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Shared pytest fixtures. Each test gets its own in-memory SQLite database
# (via dependency override), never touching the real DATABASE_URL file.

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  ensures every model is registered on Base.metadata
from app.core import cache
from app.core.rate_limit import limiter
from app.db.base import Base
from app.deps import (
    get_db,
    get_ingestion_enqueuer,
    get_memory_enqueuer,
    get_session_factory,
    get_vector_repository_factory,
)
from app.main import app
from app.memory.long_term_factory import get_memory_repository
from app.models.user import UserRole
from app.providers.embeddings.factory import get_embedding_provider
from app.providers.llm.factory import get_llm_provider
from app.providers.reranker.factory import get_reranker
from app.providers.websearch.factory import get_web_search_provider
from app.repositories import department_repository, user_repository
from app.services import ingestion_service, memory_service
from app.storage.factory import get_storage_backend
from app.storage.local_storage import LocalStorageBackend
from app.vectorstore.factory import get_vector_repository
from tests.fakes import (
    FakeEmbeddingProvider,
    FakeLLMProvider,
    FakeMemoryRepository,
    FakeReranker,
    FakeVectorRepository,
    FakeWebSearchProvider,
)


@pytest.fixture(autouse=True)
def _isolated_cache(monkeypatch):
    # app/core/cache.py talks to a real, process-wide (lru_cache'd) Redis
    # client — if a dev machine happens to have Redis running while pytest
    # runs, cache keys like "cache:departments:all" would leak real state
    # across test runs. Force every test onto its own isolated fake client
    # instead, regardless of what's actually running locally.
    store: dict[str, str] = {}

    class _FakeClient:
        def get(self, key: str) -> str | None:
            return store.get(key)

        def set(self, key: str, value: str, ex: int | None = None) -> None:
            store[key] = value

        def delete(self, key: str) -> None:
            store.pop(key, None)

    monkeypatch.setattr(cache, "_get_client", lambda: _FakeClient())


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    # limiter is a module-level singleton with process-wide in-memory
    # storage — without a reset, one test's requests count toward the next
    # test's limit, and a 150-test suite would eventually 429 unrelated
    # tests. Every test starts with a clean slate instead.
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def fake_vector_repository() -> FakeVectorRepository:
    return FakeVectorRepository()


@pytest.fixture()
def fake_llm_provider() -> FakeLLMProvider:
    return FakeLLMProvider()


@pytest.fixture()
def fake_memory_repository() -> FakeMemoryRepository:
    return FakeMemoryRepository()


@pytest.fixture()
def fake_web_search_provider() -> FakeWebSearchProvider:
    return FakeWebSearchProvider()


@pytest.fixture()
def client(
    db_session: Session,
    tmp_path,
    fake_vector_repository: FakeVectorRepository,
    fake_llm_provider: FakeLLMProvider,
    fake_memory_repository: FakeMemoryRepository,
    fake_web_search_provider: FakeWebSearchProvider,
) -> TestClient:
    def override_get_db():
        yield db_session

    # stream_reply opens its own DB session (see app/deps.py:get_session_factory)
    # since FastAPI closes Depends(get_db) before an SSE generator finishes.
    # Binding a fresh sessionmaker to db_session's own engine (StaticPool: one
    # shared in-memory connection) keeps it seeing the same test data.
    test_session_factory = sessionmaker(bind=db_session.get_bind())

    test_storage = LocalStorageBackend(root=str(tmp_path / "storage"))
    fake_embedding_provider = FakeEmbeddingProvider()

    def override_get_ingestion_enqueuer():
        # No real Celery/Redis in tests: ingestion runs synchronously, right
        # here, against the same test DB/storage/fake vector store — so
        # upload tests get genuine end-to-end coverage of the pipeline
        # without needing any live service.
        def enqueue(version_id: int) -> None:
            ingestion_service.ingest_document_version(
                db_session,
                storage=test_storage,
                embedding_provider=fake_embedding_provider,
                vector_repository=fake_vector_repository,
                version_id=version_id,
            )

        return enqueue

    def override_get_memory_enqueuer():
        # No real Celery/Redis in tests: summarization runs synchronously,
        # right here, against the same test DB/fakes — same rationale as
        # override_get_ingestion_enqueuer above.
        def enqueue(session_id: int) -> None:
            memory_service.summarize_session_memory(
                db_session,
                embedding_provider=fake_embedding_provider,
                llm_provider=fake_llm_provider,
                memory_repository=fake_memory_repository,
                session_id=session_id,
            )

        return enqueue

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_session_factory] = lambda: test_session_factory
    app.dependency_overrides[get_storage_backend] = lambda: test_storage
    app.dependency_overrides[get_vector_repository] = lambda: fake_vector_repository
    app.dependency_overrides[get_vector_repository_factory] = lambda: (lambda: fake_vector_repository)
    app.dependency_overrides[get_ingestion_enqueuer] = override_get_ingestion_enqueuer
    app.dependency_overrides[get_embedding_provider] = lambda: fake_embedding_provider
    app.dependency_overrides[get_reranker] = lambda: FakeReranker()
    app.dependency_overrides[get_llm_provider] = lambda: fake_llm_provider
    app.dependency_overrides[get_memory_repository] = lambda: fake_memory_repository
    app.dependency_overrides[get_web_search_provider] = lambda: fake_web_search_provider
    app.dependency_overrides[get_memory_enqueuer] = override_get_memory_enqueuer
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _approve_for_tests(db_session: Session, email: str) -> None:
    """New registrations are is_active=False with no department (see
    auth_service.register_user) until an admin approves them — real admin
    approval is exercised directly in tests/test_auth.py. Every other test
    just needs a usable authenticated user, so bypass the real admin API
    and approve straight in the DB instead of routing every fixture/helper
    through it."""
    user = user_repository.get_by_email(db_session, email)
    user_repository.update(db_session, user, is_active=True)
    department = department_repository.get_by_name(db_session, "Default")
    if department is None:
        department = department_repository.create(db_session, name="Default", description=None)
    user_repository.set_departments(db_session, user, [department])


def register_and_login(
    client: TestClient, db_session: Session, *, email: str, password: str, full_name: str
) -> dict:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )
    _approve_for_tests(db_session, email)
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return response.json()


@pytest.fixture()
def user_tokens(client: TestClient, db_session: Session) -> dict:
    return register_and_login(
        client,
        db_session,
        email="user@example.com",
        password="UserPass123",
        full_name="Regular User",
    )


@pytest.fixture()
def admin_tokens(client: TestClient, db_session: Session) -> dict:
    tokens = register_and_login(
        client,
        db_session,
        email="admin@example.com",
        password="AdminPass123",
        full_name="Admin User",
    )
    admin = user_repository.get_by_email(db_session, "admin@example.com")
    user_repository.update(db_session, admin, role=UserRole.ADMIN)
    # Tokens were issued before the promotion but carry no role claim (the
    # API always re-checks the DB), so they're still valid for admin calls.
    return tokens
