import time
import math
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.config import settings
from app.models.document import Document, DocumentChunk
from app.models.metrics import RetrievalMetric
from app.services.embeddings import embedding_service
from app.services.reranker import reranker_service

logger = logging.getLogger(__name__)


def compute_cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a, b in zip(vec_a, vec_b)))  # or sum(a*a)
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class RetrievalService:
    def __init__(self):
        self.k_rrf = settings.RRF_K_CONSTANT

    def search_dense(
        self,
        db: Session,
        workspace_id: str,
        query_vector: List[float],
        top_k: int,
        document_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves top_k chunks using dense vector cosine similarity.
        Uses pgvector on PostgreSQL; in-memory dot product on SQLite.
        """
        dialect = db.bind.dialect.name if db.bind else "sqlite"
        if dialect == "postgresql":
            # PostgreSQL pgvector query
            filter_clauses = ["c.workspace_id = :workspace_id"]
            params: Dict[str, Any] = {
                "workspace_id": workspace_id,
                "query_vector": str(query_vector),
                "top_k": top_k,
            }
            if document_ids:
                filter_clauses.append("c.document_id = ANY(:doc_ids)")
                params["doc_ids"] = document_ids

            sql = f"""
                SELECT c.id, c.document_id, d.filename as document_name, c.page_number, c.content,
                       1 - (c.embedding <=> :query_vector::vector) as similarity
                FROM document_chunks c
                JOIN documents d ON c.document_id = d.id
                WHERE {' AND '.join(filter_clauses)}
                ORDER BY c.embedding <=> :query_vector::vector
                LIMIT :top_k;
            """
            try:
                results = db.execute(text(sql), params).fetchall()
                return [
                    {
                        "chunk_id": str(r[0]),
                        "document_id": str(r[1]),
                        "document_name": r[2],
                        "page_number": r[3],
                        "content": r[4],
                        "score": float(r[5]),
                    }
                    for r in results
                ]
            except Exception as e:
                logger.warning(f"pgvector query failed ({e}). Falling back to ORM retrieval.")

        # Fallback dense retrieval
        query = (
            db.query(DocumentChunk, Document.filename)
            .join(Document, DocumentChunk.document_id == Document.id)
            .filter(DocumentChunk.workspace_id == workspace_id)
        )
        if document_ids:
            query = query.filter(DocumentChunk.document_id.in_(document_ids))

        chunks = query.all()
        scored = []
        for chunk, doc_name in chunks:
            if chunk.embedding:
                sim = compute_cosine_similarity(query_vector, chunk.embedding)
                scored.append(
                    {
                        "chunk_id": chunk.id,
                        "document_id": chunk.document_id,
                        "document_name": doc_name,
                        "page_number": chunk.page_number,
                        "content": chunk.content,
                        "score": round(sim, 4),
                    }
                )

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def search_sparse(
        self,
        db: Session,
        workspace_id: str,
        query_text: str,
        top_k: int,
        document_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves top_k chunks using full-text search.
        Uses PostgreSQL websearch_to_tsquery or lexical fallback.
        """
        dialect = db.bind.dialect.name if db.bind else "sqlite"
        if dialect == "postgresql":
            filter_clauses = [
                "c.workspace_id = :workspace_id",
                "c.tsv_content @@ websearch_to_tsquery('english', :query)",
            ]
            params: Dict[str, Any] = {
                "workspace_id": workspace_id,
                "query": query_text,
                "top_k": top_k,
            }
            if document_ids:
                filter_clauses.append("c.document_id = ANY(:doc_ids)")
                params["doc_ids"] = document_ids

            sql = f"""
                SELECT c.id, c.document_id, d.filename as document_name, c.page_number, c.content,
                       ts_rank_cd(c.tsv_content, websearch_to_tsquery('english', :query)) as rank_score
                FROM document_chunks c
                JOIN documents d ON c.document_id = d.id
                WHERE {' AND '.join(filter_clauses)}
                ORDER BY rank_score DESC
                LIMIT :top_k;
            """
            try:
                results = db.execute(text(sql), params).fetchall()
                return [
                    {
                        "chunk_id": str(r[0]),
                        "document_id": str(r[1]),
                        "document_name": r[2],
                        "page_number": r[3],
                        "content": r[4],
                        "score": float(r[5]),
                    }
                    for r in results
                ]
            except Exception as e:
                logger.warning(f"PostgreSQL FTS query failed ({e}). Falling back to lexical scan.")

        # Lexical matching fallback
        query = (
            db.query(DocumentChunk, Document.filename)
            .join(Document, DocumentChunk.document_id == Document.id)
            .filter(DocumentChunk.workspace_id == workspace_id)
        )
        if document_ids:
            query = query.filter(DocumentChunk.document_id.in_(document_ids))

        chunks = query.all()
        query_terms = [t.lower() for t in query_text.split() if len(t) > 2]
        scored = []
        for chunk, doc_name in chunks:
            content_lower = chunk.content.lower()
            match_count = sum(content_lower.count(t) for t in query_terms)
            if match_count > 0:
                score = round(match_count / (len(chunk.content.split()) + 10), 4)
                scored.append(
                    {
                        "chunk_id": chunk.id,
                        "document_id": chunk.document_id,
                        "document_name": doc_name,
                        "page_number": chunk.page_number,
                        "content": chunk.content,
                        "score": score,
                    }
                )

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def hybrid_search(
        self,
        db: Session,
        workspace_id: str,
        query: str,
        top_k: Optional[int] = None,
        document_ids: Optional[List[str]] = None,
        enable_reranker: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Executes hybrid search (dense + sparse), merges with RRF, applies reranking, and logs metrics.
        """
        start_time = time.perf_counter()
        k = top_k or settings.TOP_K_RETRIEVAL
        use_reranker = settings.ENABLE_RERANKER if enable_reranker is None else enable_reranker

        # 1. Embed query
        query_vector = embedding_service.embed_query(query)

        # 2. Dense retrieval
        dense_results = self.search_dense(db, workspace_id, query_vector, k, document_ids)

        # 3. Sparse retrieval
        sparse_results = self.search_sparse(db, workspace_id, query, k, document_ids)

        # 4. Reciprocal Rank Fusion (RRF)
        fused_items: Dict[str, Dict[str, Any]] = {}

        # Merge dense ranks
        for rank, item in enumerate(dense_results, start=1):
            cid = item["chunk_id"]
            if cid not in fused_items:
                fused_items[cid] = {**item, "dense_rank": rank, "sparse_rank": None, "rrf_score": 0.0}
            else:
                fused_items[cid]["dense_rank"] = rank
            fused_items[cid]["rrf_score"] += 1.0 / (self.k_rrf + rank)

        # Merge sparse ranks
        for rank, item in enumerate(sparse_results, start=1):
            cid = item["chunk_id"]
            if cid not in fused_items:
                fused_items[cid] = {**item, "dense_rank": None, "sparse_rank": rank, "rrf_score": 0.0}
            else:
                fused_items[cid]["sparse_rank"] = rank
            fused_items[cid]["rrf_score"] += 1.0 / (self.k_rrf + rank)

        candidates = list(fused_items.values())
        for c in candidates:
            c["rrf_score"] = round(c["rrf_score"], 5)
            c["relevance_score"] = c["rrf_score"]

        candidates.sort(key=lambda x: x["rrf_score"], reverse=True)

        # 5. Optional Reranking Stage
        final_results = candidates[:k]
        if use_reranker and final_results:
            rerank_k = min(len(final_results), settings.RERANK_TOP_K)
            final_results = reranker_service.rerank(query, final_results, top_k=rerank_k)

        total_latency_ms = (time.perf_counter() - start_time) * 1000

        # 6. Record Observability Metric
        try:
            top_score = final_results[0]["relevance_score"] if final_results else None
            metric = RetrievalMetric(
                workspace_id=workspace_id,
                query=query,
                total_latency_ms=round(total_latency_ms, 2),
                retrieved_chunk_count=len(final_results),
                top_similarity_score=top_score,
                hybrid_dense_count=len(dense_results),
                hybrid_sparse_count=len(sparse_results),
                rerank_applied=use_reranker,
            )
            db.add(metric)
            db.commit()
        except Exception as e:
            logger.warning(f"Failed to record retrieval metric: {e}")
            db.rollback()

        return {
            "query": query,
            "total_results": len(final_results),
            "retrieval_latency_ms": round(total_latency_ms, 2),
            "rerank_applied": use_reranker,
            "results": final_results,
        }


retrieval_service = RetrievalService()
