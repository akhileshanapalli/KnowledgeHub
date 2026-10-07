import os
import uuid
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.config import settings
from app.models.user import User
from app.models.workspace import Workspace
from app.models.document import Document, DocumentChunk
from app.schemas.document import DocumentResponse, DocumentStatusResponse, DocumentChunkResponse
from app.services.storage import storage_service
from app.tasks.ingestion import process_document, process_document_sync
from app.api.deps import get_current_user, get_current_workspace

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_EXTENSIONS = {"pdf", "docx", "doc", "txt", "md"}


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: UploadFile = File(...),
    source_url: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
):
    # 1. Validate file extension
    filename = file.filename or "uploaded_file"
    ext = filename.split(".")[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '.{ext}'. Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # 2. Check file size
    file_bytes = await file.read()
    file_size = len(file_bytes)
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if file_size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB.",
        )

    # 3. Generate storage path and upload to S3/MinIO
    doc_id = str(uuid.uuid4())
    safe_filename = os.path.basename(filename)
    storage_path = f"{current_workspace.id}/{doc_id}/{safe_filename}"

    file.file.seek(0)
    storage_service.upload_file(file.file, storage_path, content_type=file.content_type)

    # 4. Create document record in database
    document = Document(
        id=doc_id,
        workspace_id=current_workspace.id,
        uploaded_by=current_user.id,
        filename=safe_filename,
        file_type=ext,
        file_size_bytes=file_size,
        storage_path=storage_path,
        source_url=source_url,
        status="uploaded",
        chunk_count=0,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    # 5. Dispatch asynchronous processing via Celery (or sync execution in eager/test mode)
    try:
        from app.tasks.celery_app import celery_app
        if celery_app.conf.task_always_eager:
            process_document_sync(document.id, db)
        else:
            process_document.delay(document.id)
    except Exception as e:
        logger.warning(f"Could not dispatch Celery task ({e}). Processing synchronously.")
        process_document_sync(document.id, db)

    db.refresh(document)
    return DocumentResponse.model_validate(document)


@router.get("", response_model=List[DocumentResponse])
def list_documents(
    db: Session = Depends(get_db),
    current_workspace: Workspace = Depends(get_current_workspace),
):
    docs = (
        db.query(Document)
        .filter(Document.workspace_id == current_workspace.id)
        .order_by(Document.created_at.desc())
        .all()
    )
    return [DocumentResponse.model_validate(d) for d in docs]


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
def get_document_status(
    document_id: str,
    db: Session = Depends(get_db),
    current_workspace: Workspace = Depends(get_current_workspace),
):
    doc = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.workspace_id == current_workspace.id,
        )
        .first()
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    return DocumentStatusResponse(
        id=doc.id,
        status=doc.status,
        chunk_count=doc.chunk_count,
        error_message=doc.error_message,
        updated_at=doc.updated_at,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document_details(
    document_id: str,
    db: Session = Depends(get_db),
    current_workspace: Workspace = Depends(get_current_workspace),
):
    doc = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.workspace_id == current_workspace.id,
        )
        .first()
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    return DocumentResponse.model_validate(doc)


@router.get("/{document_id}/chunks", response_model=List[DocumentChunkResponse])
def get_document_chunks(
    document_id: str,
    db: Session = Depends(get_db),
    current_workspace: Workspace = Depends(get_current_workspace),
):
    doc = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.workspace_id == current_workspace.id,
        )
        .first()
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    chunks = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index.asc())
        .all()
    )
    return [DocumentChunkResponse.model_validate(c) for c in chunks]


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_workspace: Workspace = Depends(get_current_workspace),
):
    doc = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.workspace_id == current_workspace.id,
        )
        .first()
    )
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Delete original file from storage
    storage_service.delete_file(doc.storage_path)

    # Delete record (chunks cascade delete automatically)
    db.delete(doc)
    db.commit()
    return None
