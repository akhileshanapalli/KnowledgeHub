import uuid
import logging
from app.db.session import SessionLocal
from app.core.security import get_password_hash
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMembership
from app.models.document import Document, DocumentChunk
from app.services.embeddings import embedding_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed")


def seed_database():
    db = SessionLocal()
    try:
        # 1. Check or create demo user
        admin_email = "admin@knowledgehub.internal"
        user = db.query(User).filter(User.email == admin_email).first()
        if not user:
            user = User(
                id=str(uuid.uuid4()),
                email=admin_email,
                hashed_password=get_password_hash("EnterprisePass123!"),
                full_name="Demo Administrator",
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info(f"Created demo user: {admin_email}")
        else:
            logger.info(f"User {admin_email} already exists.")

        # 2. Check or create workspace
        ws_name = "HQ Knowledge Core"
        workspace = (
            db.query(Workspace)
            .join(WorkspaceMembership)
            .filter(WorkspaceMembership.user_id == user.id, Workspace.name == ws_name)
            .first()
        )
        if not workspace:
            workspace = Workspace(
                id=str(uuid.uuid4()),
                name=ws_name,
                slug="hq-knowledge-core",
            )
            db.add(workspace)
            db.commit()
            db.refresh(workspace)

            membership = WorkspaceMembership(
                id=str(uuid.uuid4()),
                user_id=user.id,
                workspace_id=workspace.id,
                role="owner",
            )
            db.add(membership)
            db.commit()
            logger.info(f"Created demo workspace: {ws_name} ({workspace.id})")
        else:
            logger.info(f"Workspace {ws_name} already exists.")

        # 3. Check or create demo document
        doc_filename = "KnowledgeHub_Platform_Guide.md"
        doc = (
            db.query(Document)
            .filter(Document.workspace_id == workspace.id, Document.filename == doc_filename)
            .first()
        )
        if not doc:
            doc = Document(
                id=str(uuid.uuid4()),
                workspace_id=workspace.id,
                uploaded_by=user.id,
                filename=doc_filename,
                file_type="md",
                file_size_bytes=4096,
                storage_path=f"workspaces/{workspace.id}/raw/{doc_filename}",
                status="completed",
                chunk_count=4,
            )
            db.add(doc)
            db.commit()
            db.refresh(doc)

            chunks_text = [
                (
                    1,
                    "KnowledgeHub Enterprise Security Standard: All data in transit requires TLS 1.3 encryption. "
                    "Data at rest is secured via AES-256 envelope encryption. Passwords require bcrypt hashing with cost factor 12. "
                    "Strict multi-tenant isolation guarantees that queries only retrieve chunks from the user's active workspace."
                ),
                (
                    2,
                    "Document Ingestion & Storage Architecture: KnowledgeHub ingests PDF, DOCX, TXT, and Markdown files asynchronously. "
                    "Original binary files are stored in S3/MinIO object storage. The text extraction pipeline normalizes headers and tables, "
                    "splitting content into recursive 800-character chunks with a 150-character sliding overlap."
                ),
                (
                    3,
                    "Hybrid Search and Reciprocal Rank Fusion: KnowledgeHub employs a two-stage retrieval pipeline. "
                    "Stage 1 executes parallel pgvector cosine similarity search and PostgreSQL tsvector BM25-style lexical search. "
                    "Results are merged using Reciprocal Rank Fusion (RRF with constant k=60). Stage 2 applies cross-encoder neural reranking."
                ),
                (
                    4,
                    "Grounded Generation & Citation Engine: LLM responses are strictly constrained to retrieved context chunks. "
                    "If the answer cannot be found in the provided context, the system returns 'I could not find information about that in the provided workspace documents.' "
                    "Every claim includes inline citations linking back to document name, chunk index, and page number."
                ),
            ]

            embeddings = embedding_service.embed_texts([c[1] for c in chunks_text])

            for idx, (page, text_content) in enumerate(chunks_text):
                chunk = DocumentChunk(
                    id=str(uuid.uuid4()),
                    workspace_id=workspace.id,
                    document_id=doc.id,
                    chunk_index=idx,
                    page_number=page,
                    content=text_content,
                    token_count=len(text_content.split()),
                    embedding=embeddings[idx] if idx < len(embeddings) else None,
                    tsv_content=text_content,
                )
                db.add(chunk)

            db.commit()
            logger.info(f"Seeded document and 4 chunks for {doc_filename}")
        else:
            logger.info(f"Document {doc_filename} already exists.")

        print("Database seed completed successfully.")

    except Exception as e:
        db.rollback()
        logger.error(f"Seeding failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
