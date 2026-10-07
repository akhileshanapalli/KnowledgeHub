import pytest
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMembership
from app.models.document import Document, DocumentChunk
from app.models.chat import Conversation, Message, MessageCitation, UserFeedback
from app.models.metrics import RetrievalMetric


def test_user_creation_and_constraints(db_session: Session):
    user = User(email="alice@company.com", hashed_password="secret_hashed_password", full_name="Alice")
    db_session.add(user)
    db_session.commit()
    assert user.id is not None
    assert user.is_active is True

    # Test unique email constraint
    duplicate = User(email="alice@company.com", hashed_password="another_password")
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_workspace_membership_and_multi_tenancy(db_session: Session, sample_user: User):
    ws1 = Workspace(name="Engineering", slug="engineering")
    ws2 = Workspace(name="Finance", slug="finance")
    db_session.add_all([ws1, ws2])
    db_session.commit()

    m1 = WorkspaceMembership(user_id=sample_user.id, workspace_id=ws1.id, role="admin")
    m2 = WorkspaceMembership(user_id=sample_user.id, workspace_id=ws2.id, role="member")
    db_session.add_all([m1, m2])
    db_session.commit()

    # Verify relationships
    assert len(sample_user.memberships) == 2
    user_ws_ids = {m.workspace_id for m in sample_user.memberships}
    assert ws1.id in user_ws_ids
    assert ws2.id in user_ws_ids


def test_document_and_chunk_cascade(db_session: Session, sample_document: Document):
    doc_id = sample_document.id
    ws_id = sample_document.workspace_id

    # Verify chunks exist
    chunks = db_session.query(DocumentChunk).filter(DocumentChunk.document_id == doc_id).all()
    assert len(chunks) == 2
    assert chunks[0].embedding is not None
    assert len(chunks[0].embedding) == 1536

    # Verify cascade delete when document is deleted
    db_session.delete(sample_document)
    db_session.commit()

    remaining_chunks = db_session.query(DocumentChunk).filter(DocumentChunk.document_id == doc_id).all()
    assert len(remaining_chunks) == 0


def test_conversation_message_and_citations(db_session: Session, sample_workspace: Workspace, sample_user: User, sample_document: Document):
    conv = Conversation(workspace_id=sample_workspace.id, user_id=sample_user.id, title="HR Policy Chat")
    db_session.add(conv)
    db_session.commit()

    msg = Message(conversation_id=conv.id, sender="assistant", content="Remote work allows up to 3 days/week.")
    db_session.add(msg)
    db_session.commit()

    chunk = sample_document.chunks[1]
    citation = MessageCitation(
        message_id=msg.id,
        chunk_id=chunk.id,
        document_name=sample_document.filename,
        page_number=2,
        excerpt="Remote work policy permits up to 3 days per week work from home.",
        relevance_score=0.95,
    )
    db_session.add(citation)
    db_session.commit()

    assert len(msg.citations) == 1
    assert msg.citations[0].document_name == "company_handbook.pdf"
    assert msg.citations[0].relevance_score == 0.95


def test_retrieval_metric_logging(db_session: Session, sample_workspace: Workspace):
    metric = RetrievalMetric(
        workspace_id=sample_workspace.id,
        query="What is the remote work policy?",
        total_latency_ms=124.5,
        retrieved_chunk_count=3,
        top_similarity_score=0.88,
        hybrid_dense_count=2,
        hybrid_sparse_count=2,
        rerank_applied=True,
    )
    db_session.add(metric)
    db_session.commit()

    stored = db_session.query(RetrievalMetric).filter(RetrievalMetric.workspace_id == sample_workspace.id).first()
    assert stored is not None
    assert stored.total_latency_ms == 124.5
    assert stored.rerank_applied is True
