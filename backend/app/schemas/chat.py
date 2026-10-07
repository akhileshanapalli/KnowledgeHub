from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class ChatMessageRequest(BaseModel):
    conversation_id: Optional[str] = Field(default=None, description="Existing conversation ID or null for new")
    message: str = Field(..., min_length=1, description="User question or prompt")
    document_ids: Optional[List[str]] = Field(default=None, description="Optional document filter")
    stream: bool = Field(default=True, description="Whether to stream response via SSE")


class MessageCitationSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    chunk_id: str
    document_name: str
    page_number: Optional[int] = None
    excerpt: str
    relevance_score: float


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    sender: str
    content: str
    retrieval_latency_ms: Optional[float] = None
    generation_latency_ms: Optional[float] = None
    citations: List[MessageCitationSchema] = []
    created_at: datetime


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: List[MessageResponse] = []


class FeedbackCreate(BaseModel):
    message_id: str
    score: int = Field(..., ge=-1, le=1, description="1 for positive, -1 for negative")
    comment: Optional[str] = None


class FeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    message_id: str
    score: int
    comment: Optional[str] = None
    created_at: datetime
