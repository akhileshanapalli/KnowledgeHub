from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class MetricEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    query: str
    total_latency_ms: float
    retrieved_chunk_count: int
    top_similarity_score: Optional[float] = None
    hybrid_dense_count: int
    hybrid_sparse_count: int
    rerank_applied: bool
    created_at: datetime


class MetricsSummary(BaseModel):
    total_queries: int
    avg_latency_ms: float
    avg_retrieved_chunks: float
    avg_top_similarity_score: float
    rerank_usage_percentage: float
    recent_queries: List[MetricEntry]
