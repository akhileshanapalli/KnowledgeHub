import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.db.session import get_db
from app.core.security import create_access_token
from app.core.rate_limit import reset_rate_limit_store
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMembership
from app.models.document import Document, DocumentChunk
from app.services.retrieval import retrieval_service
from app.services.reranker import reranker_service


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


def test_hybrid_search_and_rrf_scoring(db_session: Session, sample_workspace: Workspace, sample_user: User):
    # Create document with specific facts
    doc = Document(
        workspace_id=sample_workspace.id,
        uploaded_by=sample_user.id,
        filename="security_architecture.pdf",
        file_type="pdf",
        file_size_bytes=4096,
        storage_path="test/sec.pdf",
        status="completed",
        chunk_count=3,
    )
    db_session.add(doc)
    db_session.flush()

    chunk1 = DocumentChunk(
        workspace_id=sample_workspace.id,
        document_id=doc.id,
        chunk_index=0,
        page_number=1,
        content="Authentication uses short-lived JSON Web Tokens (JWT) signed with HMAC-SHA256.",
        embedding=[0.3] * 1536,
        tsv_content="authentication uses short lived json web tokens jwt signed hmac sha256",
    )
    chunk2 = DocumentChunk(
        workspace_id=sample_workspace.id,
        document_id=doc.id,
        chunk_index=1,
        page_number=2,
        content="PostgreSQL pgvector extension stores 1536-dimensional embeddings with HNSW indexing.",
        embedding=[0.1] * 1536,
        tsv_content="postgresql pgvector extension stores 1536 dimensional embeddings hnsw indexing",
    )
    chunk3 = DocumentChunk(
        workspace_id=sample_workspace.id,
        document_id=doc.id,
        chunk_index=2,
        page_number=3,
        content="MinIO S3-compatible object storage persists encrypted raw documents.",
        embedding=[0.05] * 1536,
        tsv_content="minio s3 compatible object storage persists encrypted raw documents",
    )
    db_session.add_all([chunk1, chunk2, chunk3])
    db_session.commit()

    # Search for JWT authentication
    results = retrieval_service.hybrid_search(
        db=db_session,
        workspace_id=sample_workspace.id,
        query="JWT tokens HMAC-SHA256 authentication",
        top_k=2,
        enable_reranker=False,
    )

    assert results["total_results"] >= 1
    top_chunk = results["results"][0]
    assert "JWT" in top_chunk["content"]
    assert top_chunk["rrf_score"] > 0


def test_reranker_reordering(db_session: Session, sample_workspace: Workspace, sample_user: User):
    candidates = [
        {
            "chunk_id": "c1",
            "document_id": "d1",
            "document_name": "guide.pdf",
            "page_number": 1,
            "content": "General introduction to distributed systems and cloud networks.",
            "rrf_score": 0.03,
        },
        {
            "chunk_id": "c2",
            "document_id": "d1",
            "document_name": "guide.pdf",
            "page_number": 2,
            "content": "Specific disaster recovery protocol: Failover completes in under 30 seconds using DNS swap.",
            "rrf_score": 0.025,
        },
    ]

    reranked = reranker_service.rerank("disaster recovery failover DNS swap", candidates, top_k=2)
    assert len(reranked) == 2
    # The chunk with exact recovery keywords should be boosted to rank 1
    assert "disaster recovery" in reranked[0]["content"].lower()
    assert reranked[0]["rerank_score"] > reranked[1]["rerank_score"]


def test_hybrid_search_tenant_isolation(client: TestClient, db_session: Session):
    # Workspace A
    user_a = User(email="usera@corp.com", hashed_password="pw", full_name="User A")
    ws_a = Workspace(name="WS A", slug="ws-a")
    db_session.add_all([user_a, ws_a])
    db_session.flush()
    db_session.add(WorkspaceMembership(user_id=user_a.id, workspace_id=ws_a.id, role="owner"))

    doc_a = Document(
        workspace_id=ws_a.id,
        uploaded_by=user_a.id,
        filename="secret_a.txt",
        file_type="txt",
        file_size_bytes=100,
        storage_path="a/secret.txt",
        status="completed",
        chunk_count=1,
    )
    db_session.add(doc_a)
    db_session.flush()

    chunk_a = DocumentChunk(
        workspace_id=ws_a.id,
        document_id=doc_a.id,
        chunk_index=0,
        page_number=1,
        content="Confidential Revenue Numbers for Org A: $50 Million in Q3.",
        embedding=[0.9] * 1536,
        tsv_content="confidential revenue numbers org a 50 million q3",
    )
    db_session.add(chunk_a)

    # Workspace B
    user_b = User(email="userb@corp.com", hashed_password="pw", full_name="User B")
    ws_b = Workspace(name="WS B", slug="ws-b")
    db_session.add_all([user_b, ws_b])
    db_session.flush()
    db_session.add(WorkspaceMembership(user_id=user_b.id, workspace_id=ws_b.id, role="owner"))

    db_session.commit()

    token_b = create_access_token(user_b.id)

    # User B queries for Confidential Revenue Numbers -> Must return ZERO results from Workspace A!
    res = client.post(
        "/api/v1/search/hybrid",
        headers={"Authorization": f"Bearer {token_b}", "X-Workspace-ID": ws_b.id},
        json={"query": "Confidential Revenue Numbers $50 Million"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total_results"] == 0
    assert len(data["results"]) == 0
