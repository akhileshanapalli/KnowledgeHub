from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class DocumentChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    chunk_index: int
    page_number: Optional[int] = None
    content: str
    token_count: Optional[int] = None


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    uploaded_by: Optional[str] = None
    filename: str
    file_type: str
    file_size_bytes: int
    source_url: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    chunk_count: int
    created_at: datetime
    updated_at: datetime


class DocumentStatusResponse(BaseModel):
    id: str
    status: str
    chunk_count: int
    error_message: Optional[str] = None
    updated_at: datetime
