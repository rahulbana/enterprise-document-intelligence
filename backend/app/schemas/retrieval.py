# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
# Repo: https://github.com/rahulbana/enterprise-document-intelligence
#
# Request/response shapes for the retrieval debug endpoint (Phase 4). Not a
# chat endpoint — this just exposes what the retrieval pipeline would hand
# an LLM, for inspecting hybrid search + reranking before Phase 5 wires it
# into an actual answer.

from pydantic import BaseModel, Field


class RetrievalDebugRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)
    candidate_limit: int = Field(default=20, ge=1, le=200)
    alpha: float = Field(default=0.5, ge=0.0, le=1.0)


class RetrievedChunkRead(BaseModel):
    document_id: int
    document_version_id: int
    chunk_index: int
    content: str
    hybrid_score: float
    rerank_score: float


class RetrievalDebugResponse(BaseModel):
    query: str
    results: list[RetrievedChunkRead]
