"use client";

import React, { useState } from "react";
import {
  Search,
  Filter,
  Layers,
  FileText,
  Clock,
  Sparkles,
  Zap,
  CheckCircle2,
} from "lucide-react";
import { api } from "../../lib/api";
import { HybridSearchResponse, SearchResultChunk } from "../../lib/types";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(8);
  const [enableReranker, setEnableReranker] = useState(true);
  const [isSearching, setIsSearching] = useState(false);
  const [results, setResults] = useState<HybridSearchResponse | null>(null);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setIsSearching(true);
    try {
      const res = await api.hybridSearch(query.trim(), topK, enableReranker);
      setResults(res);
    } catch (err: any) {
      alert("Search failed: " + err.message);
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div className="space-y-8 animate-fade-in max-w-5xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-white">
          Hybrid Search & RRF Retrieval Playground
        </h1>
        <p className="text-xs text-gray-400 mt-1">
          Test semantic vector similarity combined with PostgreSQL full-text keyword search and Reciprocal Rank Fusion (RRF).
        </p>
      </div>

      {/* Query Formulation Console */}
      <div className="glass-card rounded-2xl p-6 border border-gray-800 shadow-xl">
        <form onSubmit={handleSearch} className="space-y-4">
          <div className="relative">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Enter search query or keywords (e.g. disaster recovery RTO / RPO protocol)..."
              className="w-full pl-11 pr-4 py-3 bg-gray-950/80 border border-gray-700/80 rounded-xl text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500"
            />
            <Search className="absolute left-3.5 top-3.5 h-4 w-4 text-gray-400" />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-4 pt-1">
            <div className="flex items-center space-x-6 text-xs text-gray-300">
              <label className="flex items-center space-x-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={enableReranker}
                  onChange={(e) => setEnableReranker(e.target.checked)}
                  className="rounded bg-gray-900 border-gray-700 text-indigo-600 focus:ring-0 h-4 w-4"
                />
                <span className="font-medium">Enable Reranker Stage</span>
              </label>

              <div className="flex items-center space-x-2">
                <span className="text-gray-400">Top-K Results:</span>
                <select
                  aria-label="Top-K Results Count"
                  value={topK}
                  onChange={(e) => setTopK(Number(e.target.value))}
                  className="bg-gray-900 border border-gray-700 text-gray-200 text-xs rounded-lg px-2 py-1 focus:outline-none"
                >
                  <option value={4}>4 chunks</option>
                  <option value={8}>8 chunks</option>
                  <option value={12}>12 chunks</option>
                  <option value={20}>20 chunks</option>
                </select>
              </div>
            </div>

            <button
              type="submit"
              disabled={isSearching || !query.trim()}
              className="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-xl shadow-lg shadow-indigo-600/30 flex items-center space-x-2 transition-all disabled:opacity-50"
            >
              <Zap className="h-3.5 w-3.5" />
              <span>{isSearching ? "Retrieving..." : "Execute Hybrid Search"}</span>
            </button>
          </div>
        </form>
      </div>

      {/* Results Feed */}
      {results && (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-xs text-gray-400 px-1">
            <span>
              Retrieved <strong className="text-white">{results.total_results}</strong> candidate chunks
            </span>
            <div className="flex items-center space-x-4">
              <span className="flex items-center space-x-1">
                <Clock className="h-3 w-3 text-indigo-400" />
                <span>Latency: {results.retrieval_latency_ms} ms</span>
              </span>
              <span>Rerank Applied: {results.rerank_applied ? "Yes" : "No"}</span>
            </div>
          </div>

          {results.results.length === 0 ? (
            <div className="p-12 text-center text-xs text-gray-500 glass-card rounded-2xl border border-gray-800">
              No matching chunks found in workspace documents.
            </div>
          ) : (
            results.results.map((chunk, index) => (
              <div
                key={chunk.chunk_id}
                className="glass-card rounded-2xl p-5 border border-gray-800 space-y-3 hover:border-indigo-500/30 transition-colors"
              >
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-800 pb-3">
                  <div className="flex items-center space-x-2 text-xs">
                    <span className="h-5 w-5 rounded-full bg-indigo-600/20 text-indigo-400 font-bold flex items-center justify-center text-[10px]">
                      #{index + 1}
                    </span>
                    <FileText className="h-4 w-4 text-gray-400" />
                    <span className="font-semibold text-white">{chunk.document_name}</span>
                    {chunk.page_number && (
                      <span className="text-gray-400">&bull; Page {chunk.page_number}</span>
                    )}
                  </div>

                  <div className="flex items-center space-x-2 text-[11px]">
                    <span className="px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 font-medium">
                      RRF: {chunk.rrf_score.toFixed(4)}
                    </span>
                    {chunk.rerank_score !== undefined && (
                      <span className="px-2 py-0.5 rounded bg-violet-500/10 text-violet-400 border border-violet-500/20 font-medium">
                        Rerank: {chunk.rerank_score.toFixed(4)}
                      </span>
                    )}
                    {chunk.dense_rank && (
                      <span className="text-gray-500">Vector Rank #{chunk.dense_rank}</span>
                    )}
                    {chunk.sparse_rank && (
                      <span className="text-gray-500">Keyword Rank #{chunk.sparse_rank}</span>
                    )}
                  </div>
                </div>

                <p className="text-xs text-gray-300 leading-relaxed font-mono whitespace-pre-wrap">
                  {chunk.content}
                </p>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
