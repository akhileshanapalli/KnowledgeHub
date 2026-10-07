import json
import re
import time
import logging
from typing import List, Dict, Any, Generator, Tuple
from openai import OpenAI
from app.config import settings
from app.core.guardrails import SYSTEM_PROMPT, NOT_FOUND_FALLBACK, format_retrieved_context

logger = logging.getLogger(__name__)


def extract_citations_from_text(text: str, retrieved_chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Extracts citation tags like [Doc: filename.pdf, Page: 2] or [Doc: filename.pdf]
    and maps them to retrieved chunk records.
    """
    citations = []
    seen_chunk_ids = set()

    # Regex matching [Doc: <doc_name>, Page: <page_num>] or [Doc: <doc_name>]
    pattern = re.compile(r"\[Doc:\s*([^,\]]+)(?:,\s*Page:\s*(\d+))?\]", re.IGNORECASE)
    matches = pattern.findall(text)

    for doc_name, page_str in matches:
        doc_name = doc_name.strip()
        page_num = int(page_str) if page_str else None

        # Find matching chunk
        for chunk in retrieved_chunks:
            c_name = chunk.get("document_name", "").strip()
            c_page = chunk.get("page_number")
            c_id = chunk.get("chunk_id")

            if c_id not in seen_chunk_ids:
                if doc_name.lower() in c_name.lower() or c_name.lower() in doc_name.lower():
                    if page_num is None or page_num == c_page:
                        seen_chunk_ids.add(c_id)
                        citations.append({
                            "chunk_id": c_id,
                            "document_name": c_name,
                            "page_number": c_page,
                            "excerpt": chunk.get("content", "")[:250],
                            "relevance_score": chunk.get("relevance_score", 1.0),
                        })
                        break

    # If no regex matched but chunks were retrieved and answer was generated (not fallback), include top relevant chunk
    if not citations and retrieved_chunks and NOT_FOUND_FALLBACK not in text:
        top_c = retrieved_chunks[0]
        citations.append({
            "chunk_id": top_c.get("chunk_id"),
            "document_name": top_c.get("document_name", "Document"),
            "page_number": top_c.get("page_number"),
            "excerpt": top_c.get("content", "")[:250],
            "relevance_score": top_c.get("relevance_score", 1.0),
        })

    return citations


class LLMService:
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.base_url = settings.OPENAI_BASE_URL
        self.model = settings.OPENAI_CHAT_MODEL
        self._client = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        return self._client

    def is_mock_mode(self) -> bool:
        return (
            not self.api_key
            or self.api_key.startswith("sk-placeholder")
            or settings.ENVIRONMENT == "test"
        )

    def generate_answer(
        self,
        query: str,
        retrieved_chunks: List[Dict[str, Any]],
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Generates a non-streaming answer grounded strictly in retrieved context.
        """
        if not retrieved_chunks:
            return NOT_FOUND_FALLBACK, []

        context_block = format_retrieved_context(retrieved_chunks)

        if self.is_mock_mode():
            # Offline test mode: generate factual grounded response from top chunk
            top_chunk = retrieved_chunks[0]
            # Simple check if query is supported by context
            query_words = [w.lower() for w in re.findall(r"\w+", query) if len(w) > 3]
            content_lower = top_chunk["content"].lower()
            matches = sum(1 for w in query_words if w in content_lower)

            if matches == 0 and len(query_words) > 0:
                return NOT_FOUND_FALLBACK, []

            page_ref = f", Page: {top_chunk.get('page_number')}" if top_chunk.get("page_number") else ""
            answer = (
                f"Based on the provided documentation, {top_chunk['content'][:200]}... "
                f"[Doc: {top_chunk['document_name']}{page_ref}]"
            )
            citations = extract_citations_from_text(answer, retrieved_chunks)
            return answer, citations

        # Real OpenAI call
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if conversation_history:
            messages.extend(conversation_history[-4:])  # Keep recent 4 turns

        user_content = f"{context_block}\n\nQuestion: {query}"
        messages.append({"role": "user", "content": user_content})

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore
                temperature=0.0,
            )
            answer = response.choices[0].message.content or ""
            citations = extract_citations_from_text(answer, retrieved_chunks)
            return answer, citations
        except Exception as e:
            logger.error(f"OpenAI chat completion error: {e}")
            return f"Error communicating with AI service: {str(e)}", []

    def stream_answer(
        self,
        query: str,
        retrieved_chunks: List[Dict[str, Any]],
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Generator[Dict[str, Any], None, Tuple[str, List[Dict[str, Any]]]]:
        """
        Yields streaming tokens and final citations.
        """
        if not retrieved_chunks:
            for word in NOT_FOUND_FALLBACK.split():
                yield {"type": "token", "content": word + " "}
                time.sleep(0.01)
            yield {"type": "citations", "citations": []}
            return NOT_FOUND_FALLBACK, []

        context_block = format_retrieved_context(retrieved_chunks)

        if self.is_mock_mode():
            full_text, citations = self.generate_answer(query, retrieved_chunks, conversation_history)
            for word in full_text.split():
                yield {"type": "token", "content": word + " "}
                time.sleep(0.01)
            yield {"type": "citations", "citations": citations}
            return full_text, citations

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if conversation_history:
            messages.extend(conversation_history[-4:])

        user_content = f"{context_block}\n\nQuestion: {query}"
        messages.append({"role": "user", "content": user_content})

        full_content = []
        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore
                temperature=0.0,
                stream=True,
            )
            for chunk in stream:
                token = chunk.choices[0].delta.content or ""
                if token:
                    full_content.append(token)
                    yield {"type": "token", "content": token}

            completed_text = "".join(full_content)
            citations = extract_citations_from_text(completed_text, retrieved_chunks)
            yield {"type": "citations", "citations": citations}
            return completed_text, citations
        except Exception as e:
            err_msg = f"Error during streaming: {str(e)}"
            yield {"type": "token", "content": err_msg}
            return err_msg, []


llm_service = LLMService()
