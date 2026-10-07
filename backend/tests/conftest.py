import os
import sys
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Put backend root on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import settings
from app.tasks.celery_app import celery_app

# Configure test environment
settings.ENVIRONMENT = "test"
celery_app.conf.task_always_eager = True
from app.db.base import Base
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMembership
from app.models.document import Document, DocumentChunk
from app.models.chat import Conversation, Message, MessageCitation, UserFeedback
from app.models.metrics import RetrievalMetric

from sqlalchemy.pool import StaticPool

TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session() -> Session:
    """Creates a clean fresh database session for each test."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_user(db_session: Session) -> User:
    user = User(
        email="testuser@example.com",
        hashed_password="hashed_pw_test_12345",
        full_name="Test User",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def sample_workspace(db_session: Session, sample_user: User) -> Workspace:
    ws = Workspace(name="Acme Corp", slug="acme-corp")
    db_session.add(ws)
    db_session.flush()

    membership = WorkspaceMembership(
        user_id=sample_user.id,
        workspace_id=ws.id,
        role="owner",
    )
    db_session.add(membership)
    db_session.commit()
    db_session.refresh(ws)
    return ws


@pytest.fixture
def sample_document(db_session: Session, sample_workspace: Workspace, sample_user: User) -> Document:
    doc = Document(
        workspace_id=sample_workspace.id,
        uploaded_by=sample_user.id,
        filename="company_handbook.pdf",
        file_type="pdf",
        file_size_bytes=10240,
        storage_path=f"documents/{sample_workspace.id}/test/company_handbook.pdf",
        status="completed",
        chunk_count=2,
    )
    db_session.add(doc)
    db_session.flush()

    chunk1 = DocumentChunk(
        workspace_id=sample_workspace.id,
        document_id=doc.id,
        chunk_index=0,
        page_number=1,
        content="Welcome to Acme Corp. Our core work hours are 9 AM to 5 PM EST.",
        embedding=[0.1] * 1536,
        tsv_content="welcome acme corp core work hours 9 am 5 pm est",
    )
    chunk2 = DocumentChunk(
        workspace_id=sample_workspace.id,
        document_id=doc.id,
        chunk_index=1,
        page_number=2,
        content="Remote work policy permits up to 3 days per week work from home.",
        embedding=[0.2] * 1536,
        tsv_content="remote work policy permits 3 days week home",
    )
    db_session.add_all([chunk1, chunk2])
    db_session.commit()
    db_session.refresh(doc)
    return doc
