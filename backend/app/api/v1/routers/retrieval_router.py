# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Phase 4 debug endpoint: run the retrieval pipeline (hybrid search +
# rerank) for the current user and return what it found, without answering
# anything. Lets you inspect retrieval quality before Phase 5 wires it into
# an LLM.

from fastapi import APIRouter, Depends

from app.deps import get_current_user
from app.models.user import User
from app.providers.embeddings.base import EmbeddingProvider
from app.providers.embeddings.factory import get_embedding_provider
from app.providers.reranker.base import Reranker
from app.providers.reranker.factory import get_reranker
from app.schemas.retrieval import RetrievalDebugRequest, RetrievalDebugResponse, RetrievedChunkRead
from app.services.retrieval_service import retrieve_chunks
from app.vectorstore.base import VectorRepository
from app.vectorstore.factory import get_vector_repository

router = APIRouter(
    prefix="/retrieval", tags=["retrieval"], dependencies=[Depends(get_current_user)]
)


@router.post("/debug", response_model=RetrievalDebugResponse)
def debug_retrieve(
    payload: RetrievalDebugRequest,
    current_user: User = Depends(get_current_user),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    vector_repository: VectorRepository = Depends(get_vector_repository),
    reranker: Reranker = Depends(get_reranker),
) -> RetrievalDebugResponse:
    ranked = retrieve_chunks(
        current_user=current_user,
        query=payload.query,
        embedding_provider=embedding_provider,
        vector_repository=vector_repository,
        reranker=reranker,
        top_k=payload.top_k,
        candidate_limit=payload.candidate_limit,
        alpha=payload.alpha,
    )
    return RetrievalDebugResponse(
        query=payload.query,
        results=[
            RetrievedChunkRead(
                document_id=chunk.document_id,
                document_version_id=chunk.document_version_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                hybrid_score=chunk.hybrid_score,
                rerank_score=chunk.rerank_score,
            )
            for chunk in ranked
        ],
    )
