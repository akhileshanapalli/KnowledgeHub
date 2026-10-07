import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.db.session import get_db
from app.core.security import create_access_token
from app.core.rate_limit import reset_rate_limit_store
from app.core.guardrails import NOT_FOUND_FALLBACK
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMembership
from app.models.document import Document, DocumentChunk
from app.services.llm import extract_citations_from_text


@pytest.fixture
def client(db_session: Session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    reset_rate_limit_store()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_extract_citations_utility():
    chunks = [
        {
            "chunk_id": "c100",
            "document_name": "annual_report.pdf",
            "page_number": 14,
            "content": "Gross margin increased by 4.2% driven by supply chain efficiencies.",
            "relevance_score": 0.94,
        },
        {
            "chunk_id": "c101",
            "document_name": "tech_spec.docx",
            "page_number": None,
            "content": "Database uses PostgreSQL 16 with pgvector.",
            "relevance_score": 0.88,
        },
    ]

    answer_text = (
        "In Q4, gross margin expanded significantly [Doc: annual_report.pdf, Page: 14]. "
        "The underlying database is relational [Doc: tech_spec.docx]."
    )

    citations = extract_citations_from_text(answer_text, chunks)
    assert len(citations) == 2
    assert citations[0]["document_name"] == "annual_report.pdf"
    assert citations[0]["page_number"] == 14
    assert citations[1]["document_name"] == "tech_spec.docx"


def test_chat_grounded_answer_and_anti_hallucination(client: TestClient, db_session: Session, sample_workspace: Workspace, sample_user: User):
    token = create_access_token(sample_user.id)

    # Ingest document
    doc = Document(
        workspace_id=sample_workspace.id,
        uploaded_by=sample_user.id,
        filename="server_sla.txt",
        file_type="txt",
        file_size_bytes=500,
        storage_path="test/sla.txt",
        status="completed",
        chunk_count=1,
    )
    db_session.add(doc)
    db_session.flush()

    chunk = DocumentChunk(
        workspace_id=sample_workspace.id,
        document_id=doc.id,
        chunk_index=0,
        page_number=1,
        content="Our primary server uptime SLA is guaranteed at 99.95% excluding scheduled maintenance.",
        embedding=[0.4] * 1536,
        tsv_content="primary server uptime sla guaranteed 99 95 excluding scheduled maintenance",
    )
    db_session.add(chunk)
    db_session.commit()

    # 1. Ask supported question (non-streaming)
    res = client.post(
        "/api/v1/chat/message",
        headers={"Authorization": f"Bearer {token}", "X-Workspace-ID": sample_workspace.id},
        json={
            "message": "What is the guaranteed server uptime SLA?",
            "stream": False,
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert "99.95%" in data["content"]
    assert len(data["citations"]) >= 1
    assert data["citations"][0]["document_name"] == "server_sla.txt"

    # 2. Ask completely unsupported / out-of-context question -> Anti-hallucination check!
    unsupported_res = client.post(
        "/api/v1/chat/message",
        headers={"Authorization": f"Bearer {token}", "X-Workspace-ID": sample_workspace.id},
        json={
            "message": "What is the secret recipe for Martian chocolate cookies?",
            "stream": False,
        },
    )
    assert unsupported_res.status_code == 200
    unsupported_data = unsupported_res.json()
    assert NOT_FOUND_FALLBACK in unsupported_data["content"]
    assert len(unsupported_data["citations"]) == 0


def test_chat_sse_streaming(client: TestClient, db_session: Session, sample_workspace: Workspace, sample_user: User):
    token = create_access_token(sample_user.id)

    # Ingest a chunk
    doc = Document(
        workspace_id=sample_workspace.id,
        uploaded_by=sample_user.id,
        filename="auth_guide.txt",
        file_type="txt",
        file_size_bytes=200,
        storage_path="test/auth.txt",
        status="completed",
        chunk_count=1,
    )
    db_session.add(doc)
    db_session.flush()

    chunk = DocumentChunk(
        workspace_id=sample_workspace.id,
        document_id=doc.id,
        chunk_index=0,
        page_number=1,
        content="KnowledgeHub issues JWT bearer tokens with 60 minute expiration.",
        embedding=[0.5] * 1536,
        tsv_content="knowledgehub issues jwt bearer tokens 60 minute expiration",
    )
    db_session.add(chunk)
    db_session.commit()

    # Request with stream=True
    res = client.post(
        "/api/v1/chat/message",
        headers={"Authorization": f"Bearer {token}", "X-Workspace-ID": sample_workspace.id},
        json={
            "message": "What is the expiration time for JWT bearer tokens?",
            "stream": True,
        },
    )
    assert res.status_code == 200
    assert "text/event-stream" in res.headers["content-type"]

    lines = res.text.strip().split("\n\n")
    events = [json.loads(line.replace("data: ", "")) for line in lines if line.startswith("data: ")]
    event_types = [e.get("type") for e in events]

    assert "retrieval" in event_types
    assert "token" in event_types
    assert "done" in event_types


def test_user_feedback_and_metrics_api(client: TestClient, db_session: Session, sample_workspace: Workspace, sample_user: User):
    token = create_access_token(sample_user.id)

    # Perform a chat to create a message
    chat_res = client.post(
        "/api/v1/chat/message",
        headers={"Authorization": f"Bearer {token}", "X-Workspace-ID": sample_workspace.id},
        json={"message": "Hello knowledge base", "stream": False},
    )
    assert chat_res.status_code == 200
    msg_id = chat_res.json()["id"]

    # Submit feedback on the assistant message
    fb_res = client.post(
        "/api/v1/feedback",
        headers={"Authorization": f"Bearer {token}"},
        json={"message_id": msg_id, "score": 1, "comment": "Accurate response with exact citation."},
    )
    assert fb_res.status_code == 201
    fb_data = fb_res.json()
    assert fb_data["score"] == 1
    assert fb_data["comment"] == "Accurate response with exact citation."

    # Retrieve metrics
    met_res = client.get(
        "/api/v1/metrics/retrieval",
        headers={"Authorization": f"Bearer {token}", "X-Workspace-ID": sample_workspace.id},
    )
    assert met_res.status_code == 200
    metrics_data = met_res.json()
    assert metrics_data["total_queries"] >= 1
    assert metrics_data["avg_latency_ms"] >= 0.0
