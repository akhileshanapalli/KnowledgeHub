from typing import List, Optional
from pydantic import BaseModel, Field


class HybridSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query")
    document_ids: Optional[List[str]] = Field(default=None, description="Optional filter by document IDs")
    top_k: int = Field(default=8, ge=1, le=50, description="Number of results to retrieve")
    enable_reranker: Optional[bool] = Field(default=None, description="Override reranking setting")


class SearchResultChunk(BaseModel):
    chunk_id: str
    document_id: str
    document_name: str
    page_number: Optional[int] = None
    content: str
    relevance_score: float
    dense_rank: Optional[int] = None
    sparse_rank: Optional[int] = None
    rrf_score: float
    rerank_score: Optional[float] = None


class HybridSearchResponse(BaseModel):
    query: str
    total_results: int
    retrieval_latency_ms: float
    rerank_applied: bool
    results: List[SearchResultChunk]
