from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    slug: Optional[str] = Field(default=None, min_length=2, max_length=255)


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    role: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class WorkspaceMemberAdd(BaseModel):
    user_email: str
    role: str = Field(default="member", description="owner, admin, member")
