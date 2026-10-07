import json
import os
import sys
import uuid

# Put backend root on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.config import settings
from app.db.base import Base
from app.models.workspace import Workspace
from app.models.document import Document, DocumentChunk
from app.services.chunking import chunk_extracted_pages
from app.services.extraction import ExtractedPage
from app.services.embeddings import embedding_service
from app.services.retrieval import retrieval_service
from app.services.llm import llm_service
from eval.metrics import (
    evaluate_retrieval_recall,
    evaluate_citation_correctness,
    evaluate_groundedness,
    evaluate_anti_hallucination,
)


def run_benchmark():
    settings.ENVIRONMENT = "test"
    dataset_path = os.path.join(os.path.dirname(__file__), "dataset.json")
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    # In-memory test database
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # Create evaluation workspace
    ws = Workspace(name="Evaluation Workspace", slug="eval-workspace")
    db.add(ws)
    db.commit()

    print("\n" + "=" * 60)
    print(" KNOWLEDGEHUB RAG BENCHMARK & EVALUATION RUNNER")
    print("=" * 60)
    print(f"Ingesting {len(dataset['corpus'])} benchmark documents...")

    # Ingest documents
    for doc_item in dataset["corpus"]:
        doc_id = str(uuid.uuid4())
        doc = Document(
            id=doc_id,
            workspace_id=ws.id,
            filename=doc_item["filename"],
            file_type="txt",
            file_size_bytes=len(doc_item["content"]),
            storage_path=f"eval/{doc_item['filename']}",
            status="completed",
            chunk_count=1,
        )
        db.add(doc)
        db.flush()

        pages = [ExtractedPage(page_number=1, content=doc_item["content"])]
        chunks = chunk_extracted_pages(pages, chunk_size=500, chunk_overlap=50)
        chunk_texts = [c.content for c in chunks]
        embeddings = embedding_service.embed_texts(chunk_texts)

        for i, c in enumerate(chunks):
            chunk = DocumentChunk(
                workspace_id=ws.id,
                document_id=doc.id,
                chunk_index=c.chunk_index,
                page_number=c.page_number,
                content=c.content,
                token_count=c.token_count,
                embedding=embeddings[i],
                tsv_content=" ".join(c.content.lower().split()),
            )
            db.add(chunk)

    db.commit()
    print("Corpus indexed successfully. Running evaluation queries...\n")

    results = []
    for q in dataset["questions"]:
        query = q["query"]
        expected_doc = q["expected_doc"]
        expected_kw = q["expected_keywords"]
        is_answerable = q["is_answerable"]

        # 1. Retrieval
        retrieval_res = retrieval_service.hybrid_search(
            db=db,
            workspace_id=ws.id,
            query=query,
            top_k=4,
        )
        retrieved_chunks = retrieval_res["results"]

        # 2. QA Generation
        answer, citations = llm_service.generate_answer(query, retrieved_chunks)

        # 3. Calculate metrics
        recall = evaluate_retrieval_recall(retrieved_chunks, expected_doc)
        citation_score = evaluate_citation_correctness(answer, citations, expected_doc)
        groundedness = evaluate_groundedness(answer, retrieved_chunks, expected_kw)
        anti_hallucination = evaluate_anti_hallucination(answer, is_answerable)

        results.append({
            "id": q["id"],
            "query": query,
            "answer": answer[:90] + ("..." if len(answer) > 90 else ""),
            "recall": recall,
            "citation_score": citation_score,
            "groundedness": groundedness,
            "anti_hallucination": anti_hallucination,
        })

        print(f"Query [{q['id']}]: {query}")
        print(f"  Recall@4: {recall:.2f} | Citations: {citation_score:.2f} | Groundedness: {groundedness:.2f} | Anti-Hallucination: {anti_hallucination:.2f}")
        print(f"  Answer: {answer[:120]}...\n")

    # Aggregate summaries
    avg_recall = sum(r["recall"] for r in results) / len(results)
    avg_citations = sum(r["citation_score"] for r in results) / len(results)
    avg_groundedness = sum(r["groundedness"] for r in results) / len(results)
    avg_anti_hallucination = sum(r["anti_hallucination"] for r in results) / len(results)

    print("=" * 60)
    print(" EVALUATION SUMMARY RESULTS")
    print("=" * 60)
    print(f" Retrieval Recall@4:         {avg_recall * 100:.1f}%")
    print(f" Citation Correctness:       {avg_citations * 100:.1f}%")
    print(f" Factual Groundedness:       {avg_groundedness * 100:.1f}%")
    print(f" Anti-Hallucination Guard:   {avg_anti_hallucination * 100:.1f}%")
    print("=" * 60 + "\n")

    return {
        "avg_recall": avg_recall,
        "avg_citations": avg_citations,
        "avg_groundedness": avg_groundedness,
        "avg_anti_hallucination": avg_anti_hallucination,
    }


if __name__ == "__main__":
    run_benchmark()
