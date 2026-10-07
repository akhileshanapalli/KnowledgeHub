"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  MessageSquare,
  Send,
  Plus,
  Trash2,
  FileText,
  Clock,
  Sparkles,
  ChevronDown,
  ChevronUp,
  ThumbsUp,
  ThumbsDown,
  AlertCircle,
  ExternalLink,
  ShieldCheck,
  Check,
} from "lucide-react";
import { api } from "../../lib/api";
import {
  Conversation,
  ChatMessage,
  Citation,
  DocumentItem,
} from "../../lib/types";

export default function ChatPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingText, setStreamingText] = useState("");
  const [streamingCitations, setStreamingCitations] = useState<Citation[]>([]);
  const [streamingLatency, setStreamingLatency] = useState<number | null>(null);

  // Document filtering
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [isDocFilterOpen, setIsDocFilterOpen] = useState(false);

  // Feedback states
  const [feedbackSent, setFeedbackSent] = useState<Record<string, number>>({});
  const [expandedCitations, setExpandedCitations] = useState<Record<string, boolean>>({});

  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadInitialData();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingText]);

  const loadInitialData = async () => {
    try {
      const [convs, docs] = await Promise.all([
        api.listConversations(),
        api.listDocuments(),
      ]);
      setConversations(convs);
      setDocuments(docs.filter((d) => d.status === "completed"));

      if (convs.length > 0) {
        selectConversation(convs[0].id);
      }
    } catch (err) {
      console.error("Failed to load chat data:", err);
    }
  };

  const selectConversation = async (convId: string) => {
    setActiveConvId(convId);
    try {
      const c = await api.getConversation(convId);
      setMessages(c.messages || []);
    } catch (err) {
      console.error("Failed to load conversation:", err);
    }
  };

  const handleNewConversation = () => {
    setActiveConvId(null);
    setMessages([]);
    setStreamingText("");
    setStreamingCitations([]);
  };

  const handleDeleteConversation = async (e: React.MouseEvent, convId: string) => {
    e.stopPropagation();
    if (!confirm("Delete this conversation?")) return;
    try {
      await api.deleteConversation(convId);
      setConversations((prev) => prev.filter((c) => c.id !== convId));
      if (activeConvId === convId) {
        handleNewConversation();
      }
    } catch (err: any) {
      alert("Failed to delete conversation: " + err.message);
    }
  };

  const toggleDocumentFilter = (docId: string) => {
    setSelectedDocIds((prev) =>
      prev.includes(docId) ? prev.filter((id) => id !== docId) : [...prev, docId]
    );
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    const query = inputMessage.trim();
    if (!query || isStreaming) return;

    setInputMessage("");
    setIsStreaming(true);
    setStreamingText("");
    setStreamingCitations([]);
    setStreamingLatency(null);

    // Optimistically add user message
    const tempUserMsg: ChatMessage = {
      id: "temp-user-" + Date.now(),
      conversation_id: activeConvId || "pending",
      sender: "user",
      content: query,
      citations: [],
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    let accumulatedText = "";
    let capturedCitations: Citation[] = [];

    await api.streamChatMessage(
      {
        message: query,
        conversation_id: activeConvId || undefined,
        document_ids: selectedDocIds.length > 0 ? selectedDocIds : undefined,
      },
      (token) => {
        accumulatedText += token;
        setStreamingText((prev) => prev + token);
      },
      (retrievalEvent) => {
        setStreamingLatency(retrievalEvent.retrieval_latency_ms);
      },
      (citations) => {
        capturedCitations = citations;
        setStreamingCitations(citations);
      },
      (meta) => {
        setIsStreaming(false);
        const finalAsstMsg: ChatMessage = {
          id: meta.message_id,
          conversation_id: meta.conversation_id,
          sender: "assistant",
          content: accumulatedText,
          retrieval_latency_ms: streamingLatency || undefined,
          citations: capturedCitations,
          created_at: new Date().toISOString(),
        };

        setMessages((prev) => [...prev, finalAsstMsg]);
        setStreamingText("");
        setStreamingCitations([]);

        // If new conversation, update active state & reload list
        if (!activeConvId || activeConvId !== meta.conversation_id) {
          setActiveConvId(meta.conversation_id);
          api.listConversations().then(setConversations);
        }
      },
      (err) => {
        setIsStreaming(false);
        alert("Streaming failed: " + err.message);
      }
    );
  };

  const handleFeedback = async (msgId: string, score: number) => {
    try {
      await api.submitFeedback(msgId, score);
      setFeedbackSent((prev) => ({ ...prev, [msgId]: score }));
    } catch (err: any) {
      alert("Failed to submit feedback: " + err.message);
    }
  };

  const toggleCitationExpand = (msgId: string) => {
    setExpandedCitations((prev) => ({ ...prev, [msgId]: !prev[msgId] }));
  };

  return (
    <div className="h-[calc(100vh-8.5rem)] flex gap-6 animate-fade-in">
      {/* Left Sidebar: Conversations & Filter */}
      <div className="w-72 hidden md:flex flex-col glass-card rounded-2xl border border-gray-800 overflow-hidden shrink-0">
        <div className="p-4 border-b border-gray-800 flex items-center justify-between">
          <button
            onClick={handleNewConversation}
            className="w-full py-2 px-3 rounded-xl bg-indigo-600/15 hover:bg-indigo-600/25 border border-indigo-500/30 text-indigo-400 text-xs font-semibold flex items-center justify-center space-x-2 transition-colors"
          >
            <Plus className="h-4 w-4" />
            <span>New Chat Thread</span>
          </button>
        </div>

        {/* Document Filter Accordion */}
        <div className="p-3 border-b border-gray-800 bg-gray-900/40">
          <button
            onClick={() => setIsDocFilterOpen(!isDocFilterOpen)}
            className="w-full flex items-center justify-between text-xs text-gray-300 font-medium"
          >
            <span className="flex items-center space-x-1.5">
              <FileText className="h-3.5 w-3.5 text-indigo-400" />
              <span>Filter Documents ({selectedDocIds.length || "All"})</span>
            </span>
            {isDocFilterOpen ? (
              <ChevronUp className="h-3.5 w-3.5 text-gray-400" />
            ) : (
              <ChevronDown className="h-3.5 w-3.5 text-gray-400" />
            )}
          </button>

          {isDocFilterOpen && (
            <div className="mt-2.5 max-h-40 overflow-y-auto space-y-1 pr-1 text-xs">
              {documents.length === 0 ? (
                <div className="text-[11px] text-gray-500 py-1">No indexed documents available</div>
              ) : (
                documents.map((d) => {
                  const isChecked = selectedDocIds.includes(d.id);
                  return (
                    <label
                      key={d.id}
                      className="flex items-center space-x-2 py-1 px-1.5 rounded hover:bg-gray-800/60 cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() => toggleDocumentFilter(d.id)}
                        className="rounded bg-gray-950 border-gray-700 text-indigo-600 focus:ring-0 h-3.5 w-3.5"
                      />
                      <span className="truncate text-gray-300 text-[11px]">{d.filename}</span>
                    </label>
                  );
                })
              )}
            </div>
          )}
        </div>

        {/* Conversation List */}
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {conversations.length === 0 ? (
            <div className="text-center py-8 text-xs text-gray-500">No chat history</div>
          ) : (
            conversations.map((c) => {
              const isActive = c.id === activeConvId;
              return (
                <div
                  key={c.id}
                  onClick={() => selectConversation(c.id)}
                  className={`group flex items-center justify-between px-3 py-2.5 rounded-xl text-xs cursor-pointer transition-all ${
                    isActive
                      ? "bg-indigo-600/20 text-indigo-300 border border-indigo-500/30"
                      : "text-gray-400 hover:text-gray-200 hover:bg-gray-800/40"
                  }`}
                >
                  <div className="flex items-center space-x-2 truncate">
                    <MessageSquare className="h-3.5 w-3.5 shrink-0" />
                    <span className="truncate">{c.title}</span>
                  </div>
                  <button
                    onClick={(e) => handleDeleteConversation(e, c.id)}
                    className="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-red-400 transition-opacity"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Main Chat Interface */}
      <div className="flex-1 glass-card rounded-2xl border border-gray-800 flex flex-col overflow-hidden shadow-2xl">
        {/* Chat Header */}
        <div className="p-4 border-b border-gray-800 flex items-center justify-between bg-gray-900/50">
          <div className="flex items-center space-x-3">
            <div className="h-8 w-8 rounded-xl bg-indigo-600/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
              <Sparkles className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-white">
                Strict Grounded Assistant
              </h2>
              <div className="flex items-center space-x-2 text-[10px] text-gray-400">
                <span className="flex items-center text-emerald-400 space-x-1">
                  <ShieldCheck className="h-3 w-3" />
                  <span>Prompt Injection Guard Active</span>
                </span>
                <span>&bull;</span>
                <span>
                  {selectedDocIds.length > 0
                    ? `Scoped to ${selectedDocIds.length} docs`
                    : "Workspace-wide knowledge"}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Message Feed */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
          {messages.length === 0 && !streamingText ? (
            <div className="h-full flex flex-col items-center justify-center text-center max-w-md mx-auto space-y-3">
              <div className="h-12 w-12 rounded-2xl bg-indigo-600/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
                <MessageSquare className="h-6 w-6" />
              </div>
              <h3 className="text-sm font-semibold text-white">
                Ask questions grounded strictly in workspace content
              </h3>
              <p className="text-xs text-gray-400 leading-relaxed">
                KnowledgeHub retrieves chunks via dense semantic vectors and sparse full-text search,
                merges them with RRF, and generates answers with verifiable citations.
              </p>
            </div>
          ) : (
            <>
              {messages.map((msg) => {
                const isUser = msg.sender === "user";
                const isExpanded = expandedCitations[msg.id];
                const userFeedback = feedbackSent[msg.id];

                return (
                  <div
                    key={msg.id}
                    className={`flex flex-col ${isUser ? "items-end" : "items-start"}`}
                  >
                    <div
                      className={`max-w-[85%] rounded-2xl px-4 py-3 text-xs sm:text-sm leading-relaxed ${
                        isUser
                          ? "bg-indigo-600 text-white rounded-br-sm shadow-md"
                          : "bg-gray-900/90 text-gray-200 border border-gray-800 rounded-bl-sm"
                      }`}
                    >
                      <p className="whitespace-pre-wrap">{msg.content}</p>

                      {/* Assistant latency & citation controls */}
                      {!isUser && (
                        <div className="mt-3 pt-2 border-t border-gray-800/80 flex flex-wrap items-center justify-between gap-2 text-[11px] text-gray-400">
                          <div className="flex items-center space-x-3">
                            {msg.retrieval_latency_ms && (
                              <span className="flex items-center space-x-1">
                                <Clock className="h-3 w-3 text-indigo-400" />
                                <span>Retrieval: {msg.retrieval_latency_ms}ms</span>
                              </span>
                            )}
                            {msg.citations && msg.citations.length > 0 && (
                              <button
                                onClick={() => toggleCitationExpand(msg.id)}
                                className="text-indigo-400 hover:text-indigo-300 font-medium flex items-center space-x-1"
                              >
                                <span>{msg.citations.length} Verified Sources</span>
                                {isExpanded ? (
                                  <ChevronUp className="h-3 w-3" />
                                ) : (
                                  <ChevronDown className="h-3 w-3" />
                                )}
                              </button>
                            )}
                          </div>

                          {/* Thumbs Up / Down Feedback */}
                          <div className="flex items-center space-x-1.5">
                            <button
                              onClick={() => handleFeedback(msg.id, 1)}
                              className={`p-1 rounded hover:bg-gray-800 transition-colors ${
                                userFeedback === 1 ? "text-emerald-400" : "text-gray-500"
                              }`}
                              title="Helpful & Accurate"
                            >
                              <ThumbsUp className="h-3 w-3" />
                            </button>
                            <button
                              onClick={() => handleFeedback(msg.id, -1)}
                              className={`p-1 rounded hover:bg-gray-800 transition-colors ${
                                userFeedback === -1 ? "text-red-400" : "text-gray-500"
                              }`}
                              title="Inaccurate or Missing Facts"
                            >
                              <ThumbsDown className="h-3 w-3" />
                            </button>
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Expandable Citations Drawer */}
                    {!isUser && isExpanded && msg.citations && msg.citations.length > 0 && (
                      <div className="mt-2 max-w-[85%] w-full grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                        {msg.citations.map((c, idx) => (
                          <div
                            key={c.chunk_id || idx}
                            className="p-3 rounded-xl bg-gray-950/80 border border-indigo-500/20 space-y-1.5"
                          >
                            <div className="flex items-center justify-between font-medium text-[11px] text-indigo-400">
                              <span className="truncate max-w-[150px]">{c.document_name}</span>
                              <div className="space-x-1 text-gray-400 text-[10px]">
                                {c.page_number && <span>Page {c.page_number}</span>}
                                <span className="text-indigo-300">
                                  ({(c.relevance_score * 100).toFixed(0)}% match)
                                </span>
                              </div>
                            </div>
                            <p className="text-[11px] text-gray-300 italic line-clamp-3">
                              &ldquo;{c.excerpt}&rdquo;
                            </p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}

              {/* Streaming In-Progress Assistant Bubble */}
              {isStreaming && (
                <div className="flex flex-col items-start">
                  <div className="max-w-[85%] rounded-2xl px-4 py-3 text-xs sm:text-sm leading-relaxed bg-gray-900/90 text-gray-200 border border-indigo-500/30 rounded-bl-sm">
                    <p className="whitespace-pre-wrap">{streamingText}</p>
                    <div className="mt-2 flex items-center space-x-2 text-[10px] text-indigo-400">
                      <Clock className="h-3 w-3 animate-spin" />
                      <span>Synthesizing verified grounded response...</span>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Query Input Box */}
        <form onSubmit={handleSendMessage} className="p-4 border-t border-gray-800 bg-gray-900/60">
          <div className="flex items-center space-x-3">
            <input
              type="text"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              placeholder="Ask a question grounded in your documents..."
              disabled={isStreaming}
              className="flex-1 px-4 py-3 bg-gray-950/80 border border-gray-700/80 rounded-xl text-xs sm:text-sm text-white placeholder-gray-500 focus:outline-none focus:border-indigo-500 transition-colors disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={!inputMessage.trim() || isStreaming}
              className="px-5 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs sm:text-sm shadow-lg shadow-indigo-600/30 flex items-center space-x-2 transition-all disabled:opacity-50"
            >
              <span>Send</span>
              <Send className="h-4 w-4" />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
