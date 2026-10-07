from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.session import get_db
from app.models.workspace import Workspace
from app.models.metrics import RetrievalMetric
from app.schemas.metrics import MetricsSummary, MetricEntry
from app.api.deps import get_current_workspace

router = APIRouter()


@router.get("/retrieval", response_model=MetricsSummary)
def get_retrieval_metrics(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_workspace: Workspace = Depends(get_current_workspace),
):
    query = (
        db.query(RetrievalMetric)
        .filter(RetrievalMetric.workspace_id == current_workspace.id)
        .order_by(RetrievalMetric.created_at.desc())
    )
    records = query.limit(limit).all()

    total_count = len(records)
    if total_count == 0:
        return MetricsSummary(
            total_queries=0,
            avg_latency_ms=0.0,
            avg_retrieved_chunks=0.0,
            avg_top_similarity_score=0.0,
            rerank_usage_percentage=0.0,
            recent_queries=[],
        )

    avg_latency = sum(r.total_latency_ms for r in records) / total_count
    avg_chunks = sum(r.retrieved_chunk_count for r in records) / total_count
    scores = [r.top_similarity_score for r in records if r.top_similarity_score is not None]
    avg_score = (sum(scores) / len(scores)) if scores else 0.0
    rerank_used = sum(1 for r in records if r.rerank_applied)
    rerank_pct = (rerank_used / total_count) * 100

    return MetricsSummary(
        total_queries=total_count,
        avg_latency_ms=round(avg_latency, 2),
        avg_retrieved_chunks=round(avg_chunks, 1),
        avg_top_similarity_score=round(avg_score, 3),
        rerank_usage_percentage=round(rerank_pct, 1),
        recent_queries=[MetricEntry.model_validate(r) for r in records],
    )
