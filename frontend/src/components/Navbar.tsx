"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Layers,
  FileText,
  MessageSquare,
  Search,
  Activity,
  LogOut,
  Building2,
  Plus,
} from "lucide-react";
import {
  api,
  getToken,
  removeToken,
  getActiveWorkspaceId,
  setActiveWorkspaceId,
} from "../lib/api";
import { Workspace, User } from "../lib/types";

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();

  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [activeWorkspace, setActiveWorkspace] = useState<Workspace | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [isNewWsOpen, setIsNewWsOpen] = useState(false);
  const [newWsName, setNewWsName] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    const token = getToken();
    if (!token && pathname !== "/login") {
      router.push("/login");
      return;
    }

    if (token) {
      loadUserData();
    }
  }, [pathname]);

  const loadUserData = async () => {
    try {
      const [u, wsList] = await Promise.all([
        api.getMe(),
        api.listWorkspaces(),
      ]);
      setUser(u);
      setWorkspaces(wsList);

      const savedWsId = getActiveWorkspaceId();
      const current = wsList.find((w) => w.id === savedWsId) || wsList[0];
      if (current) {
        setActiveWorkspace(current);
        setActiveWorkspaceId(current.id);
      }
    } catch (err) {
      console.error("Failed to load user or workspaces:", err);
      if (pathname !== "/login") {
        removeToken();
        router.push("/login");
      }
    }
  };

  const handleSelectWorkspace = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    if (val === "__new__") {
      setIsNewWsOpen(true);
      return;
    }
    const found = workspaces.find((w) => w.id === val);
    if (found) {
      setActiveWorkspace(found);
      setActiveWorkspaceId(found.id);
      window.location.reload();
    }
  };

  const handleCreateWorkspace = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newWsName.trim()) return;
    setIsLoading(true);
    try {
      const created = await api.createWorkspace(newWsName.trim());
      setWorkspaces((prev) => [...prev, created]);
      setActiveWorkspace(created);
      setActiveWorkspaceId(created.id);
      setIsNewWsOpen(false);
      setNewWsName("");
      window.location.reload();
    } catch (err: any) {
      alert(err.message || "Failed to create workspace");
    } finally {
      setIsLoading(false);
    }
  };

  const handleLogout = () => {
    removeToken();
    router.push("/login");
  };

  if (pathname === "/login") return null;

  const navLinks = [
    { name: "Overview", href: "/", icon: Layers },
    { name: "Documents", href: "/documents", icon: FileText },
    { name: "Chat", href: "/chat", icon: MessageSquare },
    { name: "Hybrid Search", href: "/search", icon: Search },
    { name: "Observability", href: "/metrics", icon: Activity },
  ];

  return (
    <>
      <header className="sticky top-0 z-40 w-full border-b border-gray-800 bg-[#0b0f19]/80 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          {/* Logo & Brand */}
          <div className="flex items-center space-x-8">
            <Link href="/" className="flex items-center space-x-3 group">
              <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-violet-500 flex items-center justify-center shadow-lg shadow-indigo-500/20 group-hover:scale-105 transition-transform">
                <Layers className="h-5 w-5 text-white" />
              </div>
              <div className="flex flex-col">
                <span className="text-lg font-bold tracking-tight bg-gradient-to-r from-white via-slate-100 to-indigo-200 bg-clip-text text-transparent">
                  KnowledgeHub
                </span>
                <span className="text-[10px] text-indigo-400 font-medium -mt-1 tracking-wider uppercase">
                  Enterprise RAG
                </span>
              </div>
            </Link>

            {/* Navigation tabs */}
            <nav className="hidden md:flex items-center space-x-1">
              {navLinks.map((link) => {
                const Icon = link.icon;
                const isActive = pathname === link.href;
                return (
                  <Link
                    key={link.name}
                    href={link.href}
                    className={`flex items-center space-x-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                      isActive
                        ? "bg-indigo-600/15 text-indigo-400 border border-indigo-500/30"
                        : "text-gray-400 hover:text-gray-200 hover:bg-gray-800/50"
                    }`}
                  >
                    <Icon className="h-4 w-4" />
                    <span>{link.name}</span>
                  </Link>
                );
              })}
            </nav>
          </div>

          {/* Right Action Bar */}
          <div className="flex items-center space-x-4">
            {/* Workspace Selector */}
            <div className="flex items-center space-x-2 bg-gray-900/80 border border-gray-800 rounded-lg px-2.5 py-1">
              <Building2 className="h-3.5 w-3.5 text-gray-400" />
              <select
                aria-label="Select Active Workspace"
                value={activeWorkspace?.id || ""}
                onChange={handleSelectWorkspace}
                className="bg-transparent text-xs text-gray-200 focus:outline-none cursor-pointer pr-2"
              >
                {workspaces.map((ws) => (
                  <option key={ws.id} value={ws.id} className="bg-gray-900 text-gray-200">
                    {ws.name} ({ws.role || "member"})
                  </option>
                ))}
                <option value="__new__" className="bg-gray-900 text-indigo-400 font-medium">
                  + Create Workspace...
                </option>
              </select>
            </div>

            {/* User Profile & Logout */}
            <div className="flex items-center space-x-3 pl-2 border-l border-gray-800">
              <div className="hidden sm:flex flex-col text-right">
                <span className="text-xs font-medium text-gray-200">
                  {user?.full_name || user?.email?.split("@")[0] || "User"}
                </span>
                <span className="text-[10px] text-gray-400">{user?.email}</span>
              </div>
              <button
                onClick={handleLogout}
                title="Sign out"
                className="p-1.5 rounded-lg text-gray-400 hover:text-red-400 hover:bg-gray-800 transition-colors"
              >
                <LogOut className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* New Workspace Modal */}
      {isNewWsOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="glass-card w-full max-w-md rounded-2xl p-6 shadow-2xl border border-gray-700">
            <h3 className="text-lg font-semibold text-white mb-2">Create New Tenant Workspace</h3>
            <p className="text-xs text-gray-400 mb-4">
              Workspaces provide strict, cryptographically isolated boundary partitions for documents,
              vectors, conversations, and search queries.
            </p>
            <form onSubmit={handleCreateWorkspace} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-300 mb-1">
                  Workspace Name
                </label>
                <input
                  type="text"
                  required
                  value={newWsName}
                  onChange={(e) => setNewWsName(e.target.value)}
                  placeholder="e.g. Legal Compliance & Risk"
                  className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-sm text-white focus:outline-none focus:border-indigo-500"
                />
              </div>
              <div className="flex justify-end space-x-3 pt-2">
                <button
                  type="button"
                  onClick={() => setIsNewWsOpen(false)}
                  className="px-4 py-2 text-xs font-medium text-gray-400 hover:text-white rounded-lg hover:bg-gray-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isLoading}
                  className="px-4 py-2 text-xs font-medium bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg shadow-md transition-colors"
                >
                  {isLoading ? "Creating..." : "Create Workspace"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
