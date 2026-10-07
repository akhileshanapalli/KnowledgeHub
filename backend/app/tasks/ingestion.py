import logging
import traceback
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.document import Document, DocumentChunk
from app.services.storage import storage_service
from app.services.extraction import extract_document_content
from app.services.chunking import chunk_extracted_pages
from app.services.embeddings import embedding_service
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def process_document_sync(document_id: str, db: Session) -> bool:
    """
    Synchronous implementation of document ingestion pipeline.
    Invoked directly or by the Celery worker task.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        logger.error(f"Document {document_id} not found in database.")
        return False

    try:
        # 1. Update status to processing
        doc.status = "processing"
        doc.error_message = None
        db.commit()

        # 2. Download original file from storage
        file_bytes = storage_service.download_file(doc.storage_path)

        # 3. Extract text sections / pages
        pages = extract_document_content(file_bytes, doc.file_type)
        if not pages:
            doc.status = "completed"
            doc.chunk_count = 0
            doc.error_message = "Document contained no extractable text."
            db.commit()
            return True

        # 4. Chunk document intelligently
        chunks = chunk_extracted_pages(pages)

        # 5. Generate embeddings in batch
        chunk_texts = [c.content for c in chunks]
        embeddings = embedding_service.embed_texts(chunk_texts)

        # 6. Delete old chunks if re-processing
        db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).delete()

        # 7. Persist chunks
        db_chunks = []
        for i, c in enumerate(chunks):
            emb = embeddings[i] if i < len(embeddings) else None
            # Prepare tsv_content (lowercased clean text for full-text search)
            clean_tsv = " ".join(c.content.lower().split())
            db_chunk = DocumentChunk(
                workspace_id=doc.workspace_id,
                document_id=doc.id,
                chunk_index=c.chunk_index,
                page_number=c.page_number,
                content=c.content,
                token_count=c.token_count,
                embedding=emb,
                tsv_content=clean_tsv,
            )
            db_chunks.append(db_chunk)

        db.add_all(db_chunks)
        doc.status = "completed"
        doc.chunk_count = len(db_chunks)
        doc.error_message = None
        db.commit()
        logger.info(f"Successfully processed document {doc.id} with {len(db_chunks)} chunks.")
        return True

    except Exception as e:
        db.rollback()
        err_msg = f"{str(e)}\n{traceback.format_exc()}"
        logger.error(f"Failed processing document {document_id}: {err_msg}")
        try:
            doc = db.query(Document).filter(Document.id == document_id).first()
            if doc:
                doc.status = "failed"
                doc.error_message = str(e)
                db.commit()
        except Exception:
            pass
        return False


@celery_app.task(
    bind=True,
    name="tasks.process_document",
    max_retries=3,
    default_retry_delay=10,
)
def process_document(self, document_id: str):
    db: Session = SessionLocal()
    try:
        success = process_document_sync(document_id, db)
        if not success:
            doc = db.query(Document).filter(Document.id == document_id).first()
            if doc and doc.status == "failed":
                # Don't retry non-recoverable parsing failures
                return {"status": "failed", "document_id": document_id}
            raise Exception(f"Processing failed for document {document_id}")
        return {"status": "completed", "document_id": document_id}
    except Exception as exc:
        logger.error(f"Error in Celery task process_document: {exc}")
        raise self.retry(exc=exc)
    finally:
        db.close()
