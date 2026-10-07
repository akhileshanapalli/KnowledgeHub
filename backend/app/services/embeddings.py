import math
import hashlib
import logging
from typing import List
from openai import OpenAI
from app.config import settings

logger = logging.getLogger(__name__)


def generate_mock_embedding(text: str, dimensions: int = 1536) -> List[float]:
    """
    Generates a deterministic, normalized 1536-dimensional vector for offline/testing mode.
    Words that match produce higher dot-product similarity.
    """
    vec = [0.0] * dimensions
    # Seed values based on words
    words = text.lower().split()
    for word in words:
        h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
        for i in range(16):
            idx = (h + i * 97) % dimensions
            val = ((h >> (i * 4)) & 0xFF) / 128.0 - 1.0
            vec[idx] += val

    # Add general sentence hash
    sent_hash = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
    for i in range(32):
        idx = (sent_hash + i * 47) % dimensions
        vec[idx] += 0.5

    # Normalize to unit length (L2 norm)
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [x / norm for x in vec]
    else:
        vec[0] = 1.0
    return vec


class EmbeddingService:
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.base_url = settings.OPENAI_BASE_URL
        self.model = settings.OPENAI_EMBEDDING_MODEL
        self.dimensions = settings.EMBEDDING_DIMENSIONS
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

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        if self.is_mock_mode():
            return [generate_mock_embedding(t, self.dimensions) for t in texts]

        try:
            # Batch call to OpenAI
            response = self.client.embeddings.create(
                model=self.model,
                input=texts,
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.warning(f"OpenAI embedding call failed ({e}). Falling back to mock embeddings.")
            return [generate_mock_embedding(t, self.dimensions) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        res = self.embed_texts([text])
        return res[0] if res else [0.0] * self.dimensions


embedding_service = EmbeddingService()
