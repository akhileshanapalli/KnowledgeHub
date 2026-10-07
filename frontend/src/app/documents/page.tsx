"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  Upload,
  FileText,
  Trash2,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Clock,
  Layers,
  ExternalLink,
  ChevronRight,
  X,
} from "lucide-react";
import { api } from "../../lib/api";
import { DocumentItem, DocumentChunk } from "../../lib/types";

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [sourceUrl, setSourceUrl] = useState("");
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Chunk inspection drawer
  const [selectedDoc, setSelectedDoc] = useState<DocumentItem | null>(null);
  const [chunks, setChunks] = useState<DocumentChunk[]>([]);
  const [isChunksLoading, setIsChunksLoading] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadDocuments();
    // Auto-refresh processing documents every 4 seconds
    const interval = setInterval(() => {
      setDocuments((prev) => {
        const hasProcessing = prev.some((d) => d.status === "uploaded" || d.status === "processing");
        if (hasProcessing) {
          loadDocuments(false);
        }
        return prev;
      });
    }, 4000);
    return () => clearInterval(interval);
  }, []);

  const loadDocuments = async (showLoading: boolean = true) => {
    if (showLoading) setIsLoading(true);
    try {
      const docs = await api.listDocuments();
      setDocuments(docs);
    } catch (err: any) {
      console.error("Failed to load documents:", err);
    } finally {
      if (showLoading) setIsLoading(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadError(null);
    setIsUploading(true);

    try {
      await api.uploadDocument(file, sourceUrl.trim() || undefined);
      setSourceUrl("");
      if (fileInputRef.current) fileInputRef.current.value = "";
      await loadDocuments(false);
    } catch (err: any) {
      setUploadError(err.message || "Failed to upload document");
    } finally {
      setIsUploading(false);
    }
  };

  const handleDelete = async (docId: string, filename: string) => {
    if (!confirm(`Are you sure you want to delete '${filename}'? Chunks and vectors will be permanently removed.`)) {
      return;
    }
    try {
      await api.deleteDocument(docId);
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
      if (selectedDoc?.id === docId) setSelectedDoc(null);
    } catch (err: any) {
      alert(err.message || "Failed to delete document");
    }
  };

  const handleViewChunks = async (doc: DocumentItem) => {
    setSelectedDoc(doc);
    setIsChunksLoading(true);
    try {
      const c = await api.getDocumentChunks(doc.id);
      setChunks(c);
    } catch (err: any) {
      alert("Failed to load document chunks: " + err.message);
    } finally {
      setIsChunksLoading(false);
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
  };

  return (
    <div className="space-y-8 animate-fade-in">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            Document Ingestion & Knowledge Base
          </h1>
          <p className="text-xs text-gray-400 mt-1">
            Upload PDF, DOCX, TXT, or Markdown documents. Files are stored in S3/MinIO and chunked asynchronously.
          </p>
        </div>
        <button
          onClick={() => loadDocuments(true)}
          className="inline-flex items-center space-x-2 px-3 py-2 bg-gray-900 border border-gray-800 hover:border-gray-700 rounded-xl text-xs font-medium text-gray-300 transition-colors"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          <span>Refresh Status</span>
        </button>
      </div>

      {/* Upload Dropzone Card */}
      <div className="glass-card rounded-2xl p-6 border border-gray-800">
        <div className="flex flex-col items-center justify-center border-2 border-dashed border-gray-700/80 hover:border-indigo-500/60 rounded-xl p-8 transition-colors bg-gray-900/40 text-center">
          <div className="h-12 w-12 rounded-2xl bg-indigo-600/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 mb-3">
            <Upload className="h-6 w-6" />
          </div>
          <h3 className="text-sm font-semibold text-white mb-1">
            Upload document for asynchronous RAG ingestion
          </h3>
          <p className="text-xs text-gray-400 max-w-sm mb-4">
            Supports PDF, DOCX, TXT, and Markdown files up to 50MB.
          </p>

          <div className="w-full max-w-md space-y-3 mb-4">
            <input
              type="text"
              value={sourceUrl}
              onChange={(e) => setSourceUrl(e.target.value)}
              placeholder="Optional Source URL (e.g., https://docs.company.com/handbook)"
              className="w-full px-3 py-2 bg-gray-950/80 border border-gray-700 rounded-lg text-xs text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileUpload}
            accept=".pdf,.docx,.doc,.txt,.md"
            className="hidden"
            id="file-upload-input"
          />
          <label
            htmlFor="file-upload-input"
            className={`cursor-pointer px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-lg shadow-indigo-600/20 flex items-center space-x-2 transition-all ${
              isUploading ? "opacity-50 pointer-events-none" : ""
            }`}
          >
            <Upload className="h-4 w-4" />
            <span>{isUploading ? "Uploading & Enqueuing..." : "Select Document"}</span>
          </label>
        </div>

        {uploadError && (
          <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-xs text-red-400 flex items-center space-x-2">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>{uploadError}</span>
          </div>
        )}
      </div>

      {/* Documents Table */}
      <div className="glass-card rounded-2xl border border-gray-800 overflow-hidden shadow-xl">
        <div className="p-4 border-b border-gray-800 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-white">
            Workspace Documents ({documents.length})
          </h2>
        </div>

        {isLoading ? (
          <div className="p-12 text-center text-xs text-gray-400">Loading documents...</div>
        ) : documents.length === 0 ? (
          <div className="p-12 text-center space-y-2">
            <FileText className="h-8 w-8 text-gray-600 mx-auto" />
            <div className="text-sm font-medium text-gray-300">No documents uploaded yet</div>
            <p className="text-xs text-gray-500 max-w-sm mx-auto">
              Upload your first document above to start indexing vectors into PostgreSQL with pgvector.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-gray-900/80 text-gray-400 uppercase tracking-wider font-medium text-[10px] border-b border-gray-800">
                <tr>
                  <th className="px-5 py-3">Document</th>
                  <th className="px-5 py-3">Format & Size</th>
                  <th className="px-5 py-3">Status</th>
                  <th className="px-5 py-3">Chunks</th>
                  <th className="px-5 py-3">Uploaded</th>
                  <th className="px-5 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800 text-gray-300">
                {documents.map((doc) => (
                  <tr key={doc.id} className="hover:bg-gray-900/50 transition-colors">
                    <td className="px-5 py-3.5">
                      <div className="flex items-center space-x-3">
                        <div className="h-8 w-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 shrink-0">
                          <FileText className="h-4 w-4" />
                        </div>
                        <div>
                          <div className="font-medium text-white truncate max-w-xs sm:max-w-md">
                            {doc.filename}
                          </div>
                          {doc.source_url && (
                            <a
                              href={doc.source_url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-[10px] text-indigo-400 hover:underline flex items-center space-x-1 mt-0.5"
                            >
                              <span>{doc.source_url}</span>
                              <ExternalLink className="h-2.5 w-2.5" />
                            </a>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-3.5">
                      <span className="uppercase px-2 py-0.5 rounded bg-gray-800 text-[10px] font-semibold text-gray-300 mr-2">
                        {doc.file_type}
                      </span>
                      <span className="text-gray-400">{formatFileSize(doc.file_size_bytes)}</span>
                    </td>
                    <td className="px-5 py-3.5">
                      {doc.status === "completed" && (
                        <span className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                          <CheckCircle2 className="h-3 w-3" />
                          <span>Indexed</span>
                        </span>
                      )}
                      {doc.status === "processing" && (
                        <span className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-indigo-500/10 text-indigo-400 border border-indigo-500/30 pulse-badge">
                          <Clock className="h-3 w-3 animate-spin" />
                          <span>Processing</span>
                        </span>
                      )}
                      {doc.status === "uploaded" && (
                        <span className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">
                          <Clock className="h-3 w-3" />
                          <span>Queued</span>
                        </span>
                      )}
                      {doc.status === "failed" && (
                        <span
                          title={doc.error_message || "Ingestion error"}
                          className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-red-500/10 text-red-400 border border-red-500/20 cursor-help"
                        >
                          <AlertCircle className="h-3 w-3" />
                          <span>Failed</span>
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-3.5">
                      {doc.status === "completed" ? (
                        <button
                          onClick={() => handleViewChunks(doc)}
                          className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-lg bg-gray-800/80 hover:bg-gray-800 text-gray-200 border border-gray-700 hover:border-indigo-500/40 transition-colors"
                        >
                          <Layers className="h-3 w-3 text-indigo-400" />
                          <span>{doc.chunk_count} chunks</span>
                          <ChevronRight className="h-3 w-3 text-gray-500" />
                        </button>
                      ) : (
                        <span className="text-gray-500">-</span>
                      )}
                    </td>
                    <td className="px-5 py-3.5 text-gray-400">
                      {new Date(doc.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      <button
                        onClick={() => handleDelete(doc.id, doc.filename)}
                        title="Delete document and chunks"
                        className="p-1.5 rounded-lg text-gray-400 hover:text-red-400 hover:bg-gray-800 transition-colors"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Chunks Inspection Drawer */}
      {selectedDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-end bg-black/60 backdrop-blur-sm">
          <div className="w-full max-w-2xl h-full bg-[#111827] border-l border-gray-800 shadow-2xl flex flex-col animate-slide-left p-6">
            <div className="flex items-center justify-between pb-4 border-b border-gray-800">
              <div>
                <h3 className="text-base font-semibold text-white flex items-center space-x-2">
                  <Layers className="h-4 w-4 text-indigo-400" />
                  <span>{selectedDoc.filename}</span>
                </h3>
                <p className="text-xs text-gray-400 mt-0.5">
                  Extracted {chunks.length} chunks with 1536-dim embeddings & tsvector keywords
                </p>
              </div>
              <button
                onClick={() => setSelectedDoc(null)}
                className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto py-4 space-y-3">
              {isChunksLoading ? (
                <div className="text-center py-12 text-xs text-gray-400">Loading chunks...</div>
              ) : chunks.length === 0 ? (
                <div className="text-center py-12 text-xs text-gray-400">No chunks found.</div>
              ) : (
                chunks.map((c) => (
                  <div
                    key={c.id}
                    className="p-4 rounded-xl bg-gray-900/80 border border-gray-800 space-y-2"
                  >
                    <div className="flex items-center justify-between text-[11px] text-gray-400 border-b border-gray-800/80 pb-2">
                      <span className="font-semibold text-indigo-400">Chunk #{c.chunk_index + 1}</span>
                      <div className="space-x-3">
                        {c.page_number && <span>Page {c.page_number}</span>}
                        {c.token_count && <span>~{c.token_count} tokens</span>}
                      </div>
                    </div>
                    <p className="text-xs text-gray-300 leading-relaxed font-mono whitespace-pre-wrap">
                      {c.content}
                    </p>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
