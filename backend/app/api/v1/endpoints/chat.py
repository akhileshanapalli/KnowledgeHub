import json
import time
import uuid
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.db.session import get_db, SessionLocal
from app.models.user import User
from app.models.workspace import Workspace
from app.models.chat import Conversation, Message, MessageCitation
from app.schemas.chat import (
    ChatMessageRequest,
    ConversationResponse,
    MessageResponse,
    MessageCitationSchema,
)
from app.services.retrieval import retrieval_service
from app.services.llm import llm_service
from app.api.deps import get_current_user, get_current_workspace

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conversation(
    title: Optional[str] = "New Conversation",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
):
    conv = Conversation(
        workspace_id=current_workspace.id,
        user_id=current_user.id,
        title=title or "New Conversation",
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return ConversationResponse.model_validate(conv)


@router.get("/conversations", response_model=List[ConversationResponse])
def list_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
):
    convs = (
        db.query(Conversation)
        .filter(
            Conversation.workspace_id == current_workspace.id,
            Conversation.user_id == current_user.id,
        )
        .order_by(Conversation.updated_at.desc())
        .all()
    )
    return [ConversationResponse.model_validate(c) for c in convs]


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
):
    conv = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.workspace_id == current_workspace.id,
            Conversation.user_id == current_user.id,
        )
        .first()
    )
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return ConversationResponse.model_validate(conv)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
):
    conv = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.workspace_id == current_workspace.id,
            Conversation.user_id == current_user.id,
        )
        .first()
    )
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    db.delete(conv)
    db.commit()
    return None


@router.post("/message")
def send_chat_message(
    chat_req: ChatMessageRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_workspace: Workspace = Depends(get_current_workspace),
):
    """
    Core RAG Chat API:
    1. Retrieves relevant context from workspace knowledge base.
    2. Enforces anti-hallucination and prompt injection guardrails.
    3. Streams response via SSE (Server-Sent Events) or returns JSON.
    4. Persists conversation messages and citations.
    """
    # 1. Resolve or create conversation
    conv_id = chat_req.conversation_id
    if conv_id:
        conv = (
            db.query(Conversation)
            .filter(
                Conversation.id == conv_id,
                Conversation.workspace_id == current_workspace.id,
                Conversation.user_id == current_user.id,
            )
            .first()
        )
        if not conv:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    else:
        # Auto-create conversation with title based on first query
        title_snippet = chat_req.message[:40] + ("..." if len(chat_req.message) > 40 else "")
        conv = Conversation(
            workspace_id=current_workspace.id,
            user_id=current_user.id,
            title=title_snippet,
        )
        db.add(conv)
        db.flush()
        conv_id = conv.id

    # 2. Record user message in DB
    user_msg = Message(
        conversation_id=conv.id,
        sender="user",
        content=chat_req.message,
    )
    db.add(user_msg)
    db.commit()

    # 3. Hybrid context retrieval
    retrieval_start = time.perf_counter()
    retrieval_res = retrieval_service.hybrid_search(
        db=db,
        workspace_id=current_workspace.id,
        query=chat_req.message,
        document_ids=chat_req.document_ids,
    )
    retrieval_latency_ms = (time.perf_counter() - retrieval_start) * 1000
    retrieved_chunks = retrieval_res["results"]

    # Load conversation history for context
    history_messages = (
        db.query(Message)
        .filter(Message.conversation_id == conv.id)
        .order_by(Message.created_at.asc())
        .all()
    )
    history = [{"role": m.sender, "content": m.content} for m in history_messages]

    if not chat_req.stream:
        # Non-streaming JSON response
        gen_start = time.perf_counter()
        answer, citations = llm_service.generate_answer(chat_req.message, retrieved_chunks, history)
        generation_latency_ms = (time.perf_counter() - gen_start) * 1000

        # Save assistant message
        asst_msg = Message(
            conversation_id=conv.id,
            sender="assistant",
            content=answer,
            retrieval_latency_ms=round(retrieval_latency_ms, 2),
            generation_latency_ms=round(generation_latency_ms, 2),
        )
        db.add(asst_msg)
        db.flush()

        saved_citations = []
        for c in citations:
            cit = MessageCitation(
                message_id=asst_msg.id,
                chunk_id=c["chunk_id"],
                document_name=c["document_name"],
                page_number=c.get("page_number"),
                excerpt=c["excerpt"],
                relevance_score=c["relevance_score"],
            )
            db.add(cit)
            saved_citations.append(cit)

        db.commit()
        db.refresh(asst_msg)

        return MessageResponse(
            id=asst_msg.id,
            conversation_id=conv.id,
            sender="assistant",
            content=asst_msg.content,
            retrieval_latency_ms=asst_msg.retrieval_latency_ms,
            generation_latency_ms=asst_msg.generation_latency_ms,
            citations=[
                MessageCitationSchema(
                    chunk_id=c.chunk_id,
                    document_name=c.document_name,
                    page_number=c.page_number,
                    excerpt=c.excerpt,
                    relevance_score=c.relevance_score,
                )
                for c in saved_citations
            ],
            created_at=asst_msg.created_at,
        )

    # SSE Streaming response generator
    def sse_event_stream():
        # First send retrieved citations
        initial_citations = [
            {
                "chunk_id": c["chunk_id"],
                "document_name": c["document_name"],
                "page_number": c.get("page_number"),
                "excerpt": c["content"][:200],
                "relevance_score": c["relevance_score"],
            }
            for c in retrieved_chunks
        ]
        yield f"data: {json.dumps({'type': 'retrieval', 'retrieval_latency_ms': round(retrieval_latency_ms, 2), 'citations': initial_citations})}\n\n"

        gen_start = time.perf_counter()
        full_answer_parts = []
        final_citations = []

        generator = llm_service.stream_answer(chat_req.message, retrieved_chunks, history)
        for chunk in generator:
            if chunk["type"] == "token":
                full_answer_parts.append(chunk["content"])
                yield f"data: {json.dumps(chunk)}\n\n"
            elif chunk["type"] == "citations":
                final_citations = chunk["citations"]
                yield f"data: {json.dumps(chunk)}\n\n"

        gen_latency_ms = (time.perf_counter() - gen_start) * 1000
        full_answer = "".join(full_answer_parts).strip()

        # Persist assistant message and citations to DB
        try:
            asst_msg = Message(
                conversation_id=conv.id,
                sender="assistant",
                content=full_answer,
                retrieval_latency_ms=round(retrieval_latency_ms, 2),
                generation_latency_ms=round(gen_latency_ms, 2),
            )
            db.add(asst_msg)
            db.flush()

            for c in final_citations:
                cit = MessageCitation(
                    message_id=asst_msg.id,
                    chunk_id=c["chunk_id"],
                    document_name=c["document_name"],
                    page_number=c.get("page_number"),
                    excerpt=c["excerpt"],
                    relevance_score=c["relevance_score"],
                )
                db.add(cit)

            db.commit()
            asst_id = asst_msg.id
        except Exception as e:
            logger.error(f"Error persisting streamed message: {e}")
            db.rollback()
            asst_id = str(uuid.uuid4())

        yield f"data: {json.dumps({'type': 'done', 'message_id': asst_id, 'conversation_id': conv.id})}\n\n"

    return StreamingResponse(sse_event_stream(), media_type="text/event-stream")
