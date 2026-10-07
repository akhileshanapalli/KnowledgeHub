"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  FileText,
  MessageSquare,
  Search,
  Activity,
  Shield,
  Zap,
  Cpu,
  Layers,
  ArrowRight,
  CheckCircle2,
  Clock,
} from "lucide-react";
import { api, getActiveWorkspaceId } from "../lib/api";
import { DocumentItem, MetricsSummary } from "../lib/types";

export default function DashboardPage() {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    setIsLoading(true);
    try {
      const [docs, met] = await Promise.all([
        api.listDocuments().catch(() => []),
        api.getMetrics().catch(() => null),
      ]);
      setDocuments(docs);
      setMetrics(met);
    } finally {
      setIsLoading(false);
    }
  };

  const totalChunks = documents.reduce((acc, d) => acc + (d.chunk_count || 0), 0);
  const completedDocs = documents.filter((d) => d.status === "completed").length;

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Hero Welcome Banner */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-indigo-950/70 via-gray-900 to-[#0b0f19] border border-indigo-500/20 p-8 shadow-2xl">
        <div className="absolute top-0 right-0 -mr-16 -mt-16 w-80 h-80 rounded-full bg-indigo-500/10 blur-3xl pointer-events-none" />
        <div className="relative z-10 max-w-3xl">
          <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-xs font-semibold text-indigo-400 mb-4">
            <Shield className="h-3.5 w-3.5" />
            <span>Strict Tenant-Isolated Vector RAG</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white mb-3">
            KnowledgeHub Intelligence Core
          </h1>
          <p className="text-sm sm:text-base text-gray-300 leading-relaxed mb-6">
            Upload enterprise documents (PDF, DOCX, TXT, Markdown) to ingest, chunk, and index with
            high-dimensional pgvector embeddings and PostgreSQL full-text search. Query in real-time
            with verifiable citations and zero hallucinations.
          </p>
          <div className="flex flex-wrap gap-3">
            <Link
              href="/chat"
              className="px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold shadow-lg shadow-indigo-600/30 flex items-center space-x-2 transition-all hover:scale-[1.02]"
            >
              <MessageSquare className="h-4 w-4" />
              <span>Launch RAG Chat</span>
            </Link>
            <Link
              href="/documents"
              className="px-5 py-2.5 rounded-xl bg-gray-800/80 hover:bg-gray-800 text-gray-200 text-sm font-semibold border border-gray-700 flex items-center space-x-2 transition-all hover:border-gray-600"
            >
              <FileText className="h-4 w-4" />
              <span>Manage Documents</span>
            </Link>
          </div>
        </div>
      </div>

      {/* Overview Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="glass-card glass-card-hover rounded-2xl p-5 border border-gray-800">
          <div className="flex items-center justify-between text-gray-400 mb-3">
            <span className="text-xs font-medium uppercase tracking-wider">Total Documents</span>
            <FileText className="h-4 w-4 text-indigo-400" />
          </div>
          <div className="text-2xl font-bold text-white mb-1">
            {isLoading ? "..." : documents.length}
          </div>
          <div className="text-[11px] text-gray-400 flex items-center space-x-1">
            <CheckCircle2 className="h-3 w-3 text-emerald-400" />
            <span>{completedDocs} ready for retrieval</span>
          </div>
        </div>

        <div className="glass-card glass-card-hover rounded-2xl p-5 border border-gray-800">
          <div className="flex items-center justify-between text-gray-400 mb-3">
            <span className="text-xs font-medium uppercase tracking-wider">Indexed Chunks</span>
            <Layers className="h-4 w-4 text-violet-400" />
          </div>
          <div className="text-2xl font-bold text-white mb-1">
            {isLoading ? "..." : totalChunks}
          </div>
          <div className="text-[11px] text-gray-400">
            <span>1536-dim pgvector + FTS</span>
          </div>
        </div>

        <div className="glass-card glass-card-hover rounded-2xl p-5 border border-gray-800">
          <div className="flex items-center justify-between text-gray-400 mb-3">
            <span className="text-xs font-medium uppercase tracking-wider">Total Queries</span>
            <Search className="h-4 w-4 text-cyan-400" />
          </div>
          <div className="text-2xl font-bold text-white mb-1">
            {isLoading ? "..." : metrics?.total_queries || 0}
          </div>
          <div className="text-[11px] text-gray-400">
            <span>Hybrid RRF search operations</span>
          </div>
        </div>

        <div className="glass-card glass-card-hover rounded-2xl p-5 border border-gray-800">
          <div className="flex items-center justify-between text-gray-400 mb-3">
            <span className="text-xs font-medium uppercase tracking-wider">Avg Latency</span>
            <Zap className="h-4 w-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold text-white mb-1">
            {isLoading ? "..." : `${metrics?.avg_latency_ms || 0} ms`}
          </div>
          <div className="text-[11px] text-gray-400">
            <span>Retrieval & rerank pipeline</span>
          </div>
        </div>
      </div>

      {/* Feature Navigation Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Link
          href="/documents"
          className="glass-card glass-card-hover rounded-2xl p-6 border border-gray-800 group"
        >
          <div className="h-10 w-10 rounded-xl bg-indigo-600/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 mb-4 group-hover:bg-indigo-600/20 transition-colors">
            <FileText className="h-5 w-5" />
          </div>
          <h3 className="text-base font-semibold text-white mb-2 flex items-center justify-between">
            <span>Document Ingestion</span>
            <ArrowRight className="h-4 w-4 text-gray-500 group-hover:text-indigo-400 transition-transform group-hover:translate-x-1" />
          </h3>
          <p className="text-xs text-gray-400 leading-relaxed">
            Drag-and-drop file ingestion with automatic page extraction, recursive overlap chunking,
            and background Celery task tracking.
          </p>
        </Link>

        <Link
          href="/chat"
          className="glass-card glass-card-hover rounded-2xl p-6 border border-gray-800 group"
        >
          <div className="h-10 w-10 rounded-xl bg-violet-600/10 border border-violet-500/20 flex items-center justify-center text-violet-400 mb-4 group-hover:bg-violet-600/20 transition-colors">
            <MessageSquare className="h-5 w-5" />
          </div>
          <h3 className="text-base font-semibold text-white mb-2 flex items-center justify-between">
            <span>Grounded RAG Chat</span>
            <ArrowRight className="h-4 w-4 text-gray-500 group-hover:text-violet-400 transition-transform group-hover:translate-x-1" />
          </h3>
          <p className="text-xs text-gray-400 leading-relaxed">
            Real-time SSE answer streaming with strict anti-hallucination guardrails, expandable citations,
            and relevance scores.
          </p>
        </Link>

        <Link
          href="/search"
          className="glass-card glass-card-hover rounded-2xl p-6 border border-gray-800 group"
        >
          <div className="h-10 w-10 rounded-xl bg-cyan-600/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400 mb-4 group-hover:bg-cyan-600/20 transition-colors">
            <Search className="h-5 w-5" />
          </div>
          <h3 className="text-base font-semibold text-white mb-2 flex items-center justify-between">
            <span>Hybrid Search Tester</span>
            <ArrowRight className="h-4 w-4 text-gray-500 group-hover:text-cyan-400 transition-transform group-hover:translate-x-1" />
          </h3>
          <p className="text-xs text-gray-400 leading-relaxed">
            Interactive search console comparing dense vector similarity, sparse keyword matches,
            and Reciprocal Rank Fusion (RRF) scores.
          </p>
        </Link>
      </div>

      {/* System Architecture Highlights */}
      <div className="glass-card rounded-2xl p-6 border border-gray-800">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-400 mb-4">
          Production Architecture & Guardrail Highlights
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="flex items-start space-x-3">
            <div className="p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 shrink-0">
              <Shield className="h-4 w-4" />
            </div>
            <div>
              <h4 className="text-xs font-semibold text-white mb-1">Strict Multi-Tenancy</h4>
              <p className="text-[11px] text-gray-400">
                Workspace IDs are verified at the database query level on every endpoint. No cross-tenant data leakage.
              </p>
            </div>
          </div>

          <div className="flex items-start space-x-3">
            <div className="p-2 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 shrink-0">
              <Cpu className="h-4 w-4" />
            </div>
            <div>
              <h4 className="text-xs font-semibold text-white mb-1">Hybrid RRF Retrieval</h4>
              <p className="text-[11px] text-gray-400">
                Combines semantic conceptual vectors with exact keyword matching to handle acronyms and part numbers.
              </p>
            </div>
          </div>

          <div className="flex items-start space-x-3">
            <div className="p-2 rounded-lg bg-violet-500/10 border border-violet-500/20 text-violet-400 shrink-0">
              <CheckCircle2 className="h-4 w-4" />
            </div>
            <div>
              <h4 className="text-xs font-semibold text-white mb-1">Anti-Hallucination Guard</h4>
              <p className="text-[11px] text-gray-400">
                If facts are missing from retrieved sources, the system explicitly reports that the answer was not found.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
