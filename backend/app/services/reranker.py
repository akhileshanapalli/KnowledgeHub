import re
import math
from typing import List, Dict, Any


def compute_token_relevance(query: str, text: str) -> float:
    """
    Computes lexical cross-alignment and term proximity score between query and chunk.
    """
    query_tokens = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 2]
    if not query_tokens:
        return 0.5

    text_lower = text.lower()
    text_tokens = re.findall(r"\w+", text_lower)
    if not text_tokens:
        return 0.0

    # 1. Exact phrase boost
    phrase_boost = 0.3 if query.lower() in text_lower else 0.0

    # 2. Term coverage score
    found_tokens = sum(1 for token in query_tokens if token in text_lower)
    coverage_score = found_tokens / len(query_tokens)

    # 3. Density / frequency score
    term_counts = sum(text_lower.count(token) for token in query_tokens)
    density_score = min(0.3, (term_counts / (len(text_tokens) + 10)) * 5)

    score = (0.5 * coverage_score) + phrase_boost + density_score
    return min(1.0, max(0.0, score))


class RerankerService:
    def rerank(self, query: str, candidates: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Reranks candidates based on a weighted combination of RRF score and token cross-alignment.
        """
        if not candidates:
            return []

        reranked = []
        for item in candidates:
            content = item.get("content", "")
            cross_score = compute_token_relevance(query, content)
            rrf_score = item.get("rrf_score", 0.0)

            # Combined score giving weight to both reciprocal rank and content cross-alignment
            combined_score = (0.5 * cross_score) + (0.5 * (rrf_score * 30))
            item_copy = dict(item)
            item_copy["rerank_score"] = round(combined_score, 4)
            # Update general relevance score to reflect reranking
            item_copy["relevance_score"] = round(combined_score, 4)
            reranked.append(item_copy)

        reranked.sort(key=lambda x: x["rerank_score"], reverse=True)
        return reranked[:top_k]


reranker_service = RerankerService()
