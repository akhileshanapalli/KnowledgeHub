import re
from typing import List, Dict, Any, Optional
from app.core.guardrails import NOT_FOUND_FALLBACK


def evaluate_retrieval_recall(retrieved_chunks: List[Dict[str, Any]], expected_doc: Optional[str]) -> float:
    """
    Computes Recall@K: 1.0 if target document is among retrieved chunks, 0.0 otherwise.
    For unanswerable queries (expected_doc is None), returns 1.0 if no chunks or appropriately handled.
    """
    if expected_doc is None:
        return 1.0

    for c in retrieved_chunks:
        if c.get("document_name") == expected_doc:
            return 1.0
    return 0.0


def evaluate_citation_correctness(answer: str, citations: List[Dict[str, Any]], expected_doc: Optional[str]) -> float:
    """
    Measures whether citations in the answer accurately map to ground truth source documents.
    """
    if expected_doc is None:
        # If unanswerable, there should be zero citations
        return 1.0 if len(citations) == 0 else 0.0

    if not citations:
        return 0.0

    valid_citations = [c for c in citations if c.get("document_name") == expected_doc]
    return len(valid_citations) / len(citations)


def evaluate_groundedness(answer: str, retrieved_chunks: List[Dict[str, Any]], expected_keywords: List[str]) -> float:
    """
    Measures groundedness: checks if factual keywords appear in both retrieved context and the generated answer.
    """
    if not expected_keywords:
        return 1.0 if NOT_FOUND_FALLBACK in answer else 0.5

    answer_lower = answer.lower()
    context_text = " ".join(c.get("content", "").lower() for c in retrieved_chunks)

    keyword_hits = 0
    for kw in expected_keywords:
        kw_l = kw.lower()
        if kw_l in answer_lower and kw_l in context_text:
            keyword_hits += 1

    return keyword_hits / len(expected_keywords)


def evaluate_anti_hallucination(answer: str, is_answerable: bool) -> float:
    """
    Measures anti-hallucination rate:
    - If question is answerable, answer should NOT be fallback.
    - If question is unanswerable, answer MUST be fallback.
    """
    contains_fallback = NOT_FOUND_FALLBACK in answer
    if not is_answerable:
        return 1.0 if contains_fallback else 0.0
    else:
        return 1.0 if not contains_fallback else 0.0
