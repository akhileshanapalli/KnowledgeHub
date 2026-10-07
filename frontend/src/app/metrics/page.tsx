"use client";

import React, { useState, useEffect } from "react";
import {
  Activity,
  Zap,
  Clock,
  Layers,
  Cpu,
  RefreshCw,
  Search,
  CheckCircle2,
} from "lucide-react";
import { api } from "../../lib/api";
import { MetricsSummary } from "../../lib/types";

export default function MetricsPage() {
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadMetrics();
  }, []);

  const loadMetrics = async () => {
    setIsLoading(true);
    try {
      const data = await api.getMetrics();
      setMetrics(data);
    } catch (err) {
      console.error("Failed to load metrics:", err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-8 animate-fade-in max-w-6xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            System Observability & Retrieval Metrics
          </h1>
          <p className="text-xs text-gray-400 mt-1">
            Real-time telemetry measuring hybrid retrieval latency, chunk distribution, similarity distributions, and reranker usage.
          </p>
        </div>
        <button
          onClick={loadMetrics}
          className="inline-flex items-center space-x-2 px-3 py-2 bg-gray-900 border border-gray-800 hover:border-gray-700 rounded-xl text-xs font-medium text-gray-300 transition-colors"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          <span>Refresh Telemetry</span>
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="glass-card rounded-2xl p-5 border border-gray-800">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Total Operations</span>
            <Activity className="h-4 w-4 text-indigo-400" />
          </div>
          <div className="text-2xl font-bold text-white mb-1">
            {isLoading ? "..." : metrics?.total_queries || 0}
          </div>
          <span className="text-[11px] text-gray-400">Total logged retrieval executions</span>
        </div>

        <div className="glass-card rounded-2xl p-5 border border-gray-800">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Avg Total Latency</span>
            <Clock className="h-4 w-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold text-white mb-1">
            {isLoading ? "..." : `${metrics?.avg_latency_ms || 0} ms`}
          </div>
          <span className="text-[11px] text-gray-400">Dense + Sparse + RRF total time</span>
        </div>

        <div className="glass-card rounded-2xl p-5 border border-gray-800">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Avg Retrieved Chunks</span>
            <Layers className="h-4 w-4 text-violet-400" />
          </div>
          <div className="text-2xl font-bold text-white mb-1">
            {isLoading ? "..." : metrics?.avg_retrieved_chunks || 0}
          </div>
          <span className="text-[11px] text-gray-400">Candidates per query</span>
        </div>

        <div className="glass-card rounded-2xl p-5 border border-gray-800">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs font-medium uppercase tracking-wider">Reranker Frequency</span>
            <Cpu className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-white mb-1">
            {isLoading ? "..." : `${metrics?.rerank_usage_percentage || 0}%`}
          </div>
          <span className="text-[11px] text-gray-400">Queries utilizing cross-alignment</span>
        </div>
      </div>

      {/* Telemetry Log Table */}
      <div className="glass-card rounded-2xl border border-gray-800 overflow-hidden shadow-xl">
        <div className="p-4 border-b border-gray-800">
          <h2 className="text-sm font-semibold text-white">
            Recent Retrieval Telemetry Log
          </h2>
        </div>

        {isLoading ? (
          <div className="p-12 text-center text-xs text-gray-400">Loading telemetry records...</div>
        ) : !metrics || metrics.recent_queries.length === 0 ? (
          <div className="p-12 text-center text-xs text-gray-500">
            No queries logged yet. Run a search or ask questions in Chat to generate metrics.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-gray-900/80 text-gray-400 uppercase tracking-wider font-medium text-[10px] border-b border-gray-800">
                <tr>
                  <th className="px-5 py-3">Query</th>
                  <th className="px-5 py-3">Latency</th>
                  <th className="px-5 py-3">Retrieved Chunks</th>
                  <th className="px-5 py-3">Modalities</th>
                  <th className="px-5 py-3">Reranked</th>
                  <th className="px-5 py-3">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800 text-gray-300">
                {metrics.recent_queries.map((q) => (
                  <tr key={q.id} className="hover:bg-gray-900/50 transition-colors">
                    <td className="px-5 py-3.5 font-medium text-white max-w-sm truncate">
                      {q.query}
                    </td>
                    <td className="px-5 py-3.5">
                      <span className="font-mono text-amber-400">{q.total_latency_ms} ms</span>
                    </td>
                    <td className="px-5 py-3.5">
                      <span className="font-medium text-white">{q.retrieved_chunk_count}</span>
                    </td>
                    <td className="px-5 py-3.5 text-[11px] text-gray-400">
                      Dense: {q.hybrid_dense_count} | Sparse: {q.hybrid_sparse_count}
                    </td>
                    <td className="px-5 py-3.5">
                      {q.rerank_applied ? (
                        <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[10px]">
                          Yes
                        </span>
                      ) : (
                        <span className="text-gray-500 text-[10px]">No</span>
                      )}
                    </td>
                    <td className="px-5 py-3.5 text-gray-400 text-[11px]">
                      {new Date(q.created_at).toLocaleTimeString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
