from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.workspace import Workspace
from app.schemas.retrieval import HybridSearchRequest, HybridSearchResponse, SearchResultChunk
from app.services.retrieval import retrieval_service
from app.api.deps import get_current_workspace

router = APIRouter()


@router.post("/hybrid", response_model=HybridSearchResponse)
def hybrid_search_endpoint(
    search_req: HybridSearchRequest,
    db: Session = Depends(get_db),
    current_workspace: Workspace = Depends(get_current_workspace),
):
    """
    Hybrid Search API:
    Executes dense vector similarity + sparse keyword full-text search,
    merges rankings with Reciprocal Rank Fusion (RRF), and applies reranking.
    Strictly isolated to current workspace documents.
    """
    result = retrieval_service.hybrid_search(
        db=db,
        workspace_id=current_workspace.id,
        query=search_req.query,
        top_k=search_req.top_k,
        document_ids=search_req.document_ids,
        enable_reranker=search_req.enable_reranker,
    )

    formatted_chunks = [
        SearchResultChunk(
            chunk_id=r["chunk_id"],
            document_id=r["document_id"],
            document_name=r["document_name"],
            page_number=r.get("page_number"),
            content=r["content"],
            relevance_score=r["relevance_score"],
            dense_rank=r.get("dense_rank"),
            sparse_rank=r.get("sparse_rank"),
            rrf_score=r["rrf_score"],
            rerank_score=r.get("rerank_score"),
        )
        for r in result["results"]
    ]

    return HybridSearchResponse(
        query=result["query"],
        total_results=result["total_results"],
        retrieval_latency_ms=result["retrieval_latency_ms"],
        rerank_applied=result["rerank_applied"],
        results=formatted_chunks,
    )
