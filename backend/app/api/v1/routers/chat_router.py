# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Chat session CRUD plus the streaming reply endpoint. Sessions are private
# to their owner — no department sharing, unlike documents.

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limit import limiter
from app.deps import (
    MemoryEnqueuer,
    SessionFactory,
    VectorRepositoryFactory,
    get_current_user,
    get_db,
    get_memory_enqueuer,
    get_session_factory,
    get_vector_repository_factory,
)
from app.memory.long_term_base import MemoryRepository
from app.memory.long_term_factory import get_memory_repository
from app.models.user import User
from app.providers.embeddings.base import EmbeddingProvider
from app.providers.embeddings.factory import get_embedding_provider
from app.providers.llm.base import LLMProvider
from app.providers.llm.factory import get_llm_provider
from app.providers.reranker.base import Reranker
from app.providers.reranker.factory import get_reranker
from app.providers.websearch.base import WebSearchProvider
from app.providers.websearch.factory import get_web_search_provider
from app.schemas.chat import (
    ChatMessageCreate,
    ChatMessageRead,
    ChatSessionCreate,
    ChatSessionRead,
)
from app.schemas.pagination import PageParams
from app.services import chat_service
from app.services.chat_service import ChatSessionNotFoundError

router = APIRouter(prefix="/chat", tags=["chat"], dependencies=[Depends(get_current_user)])


@router.post("/sessions", response_model=ChatSessionRead, status_code=status.HTTP_201_CREATED)
def create_chat_session(
    payload: ChatSessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatSessionRead:
    session = chat_service.create_session(db, current_user=current_user, title=payload.title)
    return ChatSessionRead.model_validate(session, from_attributes=True)


@router.get("/sessions", response_model=list[ChatSessionRead])
def list_chat_sessions(
    response: Response,
    page: PageParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChatSessionRead]:
    sessions = chat_service.list_sessions(db, current_user, limit=page.limit, offset=page.offset)
    response.headers["X-Total-Count"] = str(chat_service.count_sessions(db, current_user))
    return [ChatSessionRead.model_validate(s, from_attributes=True) for s in sessions]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    memory_repository: MemoryRepository = Depends(get_memory_repository),
) -> None:
    try:
        chat_service.delete_session(
            db, current_user, session_id, memory_repository=memory_repository
        )
    except ChatSessionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageRead])
def list_chat_messages(
    session_id: int,
    response: Response,
    page: PageParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChatMessageRead]:
    try:
        messages = chat_service.list_messages(
            db, current_user, session_id, limit=page.limit, offset=page.offset
        )
        total = chat_service.count_messages(db, current_user, session_id)
    except ChatSessionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    response.headers["X-Total-Count"] = str(total)
    return [ChatMessageRead.model_validate(m, from_attributes=True) for m in messages]


@router.post("/sessions/{session_id}/messages")
@limiter.limit(settings.RATE_LIMIT_CHAT)
def send_chat_message(
    request: Request,
    session_id: int,
    payload: ChatMessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    session_factory: SessionFactory = Depends(get_session_factory),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    vector_repository_factory: VectorRepositoryFactory = Depends(get_vector_repository_factory),
    reranker: Reranker = Depends(get_reranker),
    llm_provider: LLMProvider = Depends(get_llm_provider),
    web_search_provider: WebSearchProvider | None = Depends(get_web_search_provider),
    memory_enqueuer: MemoryEnqueuer = Depends(get_memory_enqueuer),
) -> StreamingResponse:
    # Ownership check up front (proper 404 via the request-scoped session)
    # before handing off to stream_reply, which opens its own DB session for
    # the duration of the stream — see app/deps.py:get_session_factory.
    try:
        chat_service.get_session(db, current_user, session_id)
    except ChatSessionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc

    generator = chat_service.stream_reply(
        session_factory=session_factory,
        session_id=session_id,
        current_user_id=current_user.id,
        content=payload.content,
        embedding_provider=embedding_provider,
        vector_repository_factory=vector_repository_factory,
        reranker=reranker,
        llm_provider=llm_provider,
        web_search_provider=web_search_provider,
        memory_enqueuer=memory_enqueuer,
    )
    return StreamingResponse(generator, media_type="text/event-stream")
