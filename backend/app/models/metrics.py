from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, Float, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, generate_uuid

if TYPE_CHECKING:
    from app.models.workspace import Workspace


class RetrievalMetric(Base):
    __tablename__ = "retrieval_metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True, nullable=False
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    total_latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    retrieved_chunk_count: Mapped[int] = mapped_column(Integer, nullable=False)
    top_similarity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    hybrid_dense_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hybrid_sparse_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rerank_applied: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="retrieval_metrics")
