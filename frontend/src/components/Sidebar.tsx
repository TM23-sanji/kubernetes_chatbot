"use client";

import {
  PanelLeftClose,
  PanelLeftOpen,
  SquarePen,
  Search,
  History,
  Star,
  Trash2,
} from "lucide-react";
import { useState, useEffect } from "react";
import { CornerMarkers } from "./CornerMarkers";

interface Conversation {
  id: string;
  title: string;
  starred: boolean;
  updated_at: string | null;
}

interface SidebarProps {
  open: boolean;
  onToggle: () => void;
  activeConversationId: string | null;
  onSelectConversation: (id: string | null) => void;
  onNewConversation: () => void;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Sidebar({
  open,
  onToggle,
  activeConversationId,
  onSelectConversation,
  onNewConversation,
}: SidebarProps) {
  const [showStarred, setShowStarred] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [conversations, setConversations] = useState<Conversation[]>([]);

  useEffect(() => {
    fetchConversations();
  }, [showStarred, searchQuery]);

  const fetchConversations = async () => {
    try {
      const params = new URLSearchParams();
      if (showStarred) params.set("filter", "starred");
      if (searchQuery) params.set("q", searchQuery);
      const res = await fetch(`${API_BASE}/api/conversations?${params}`);
      if (res.ok) {
        const data = await res.json();
        setConversations(data);
      }
    } catch {
      // silently fail
    }
  };

  const handleNewConversation = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/conversations`, { method: "POST" });
      if (res.ok) {
        const data = await res.json();
        onNewConversation();
        fetchConversations();
      }
    } catch {
      // silently fail
    }
  };

  const handleToggleStar = async (e: React.MouseEvent, convId: string) => {
    e.stopPropagation();
    try {
      await fetch(`${API_BASE}/api/conversations/${convId}/star`, { method: "POST" });
      fetchConversations();
    } catch {
      // silently fail
    }
  };

  const handleDelete = async (e: React.MouseEvent, convId: string) => {
    e.stopPropagation();
    try {
      await fetch(`${API_BASE}/api/conversations/${convId}`, { method: "DELETE" });
      fetchConversations();
    } catch {
      // silently fail
    }
  };

  return (
    <aside
      className={`relative flex-shrink-0 bg-sidebar border-r border-black/10 transition-all duration-200 ease-in-out flex flex-col ${
        open ? "w-64" : "w-12"
      }`}
    >
      <div className="flex items-center justify-between p-2 h-12 border-b border-black/10">
        {open && (
          <span className="text-sm font-medium text-foreground ml-1">
            Kubernetes RAG
          </span>
        )}
        <button
          onClick={onToggle}
          className="p-1.5 rounded hover:bg-sidebar-hover text-muted transition-colors"
          aria-label={open ? "Close sidebar" : "Open sidebar"}
        >
          {open ? <PanelLeftClose size={16} /> : <PanelLeftOpen size={16} />}
        </button>
      </div>

      {open && (
        <div className="flex-1 flex flex-col min-h-0">
          <div className="p-2 space-y-0.5">
            <button
              onClick={handleNewConversation}
              className="flex items-center gap-2 w-full px-2 py-1.5 rounded hover:bg-sidebar-hover text-sm text-foreground transition-colors"
            >
              <SquarePen size={14} />
              <span>New conversation</span>
            </button>
            <div className="relative">
              <Search
                size={14}
                className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted"
              />
              <input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search conversations"
                className="w-full pl-8 pr-2 py-1.5 rounded bg-transparent text-sm text-foreground placeholder-muted outline-none hover:bg-sidebar-hover focus:bg-sidebar-hover transition-colors"
              />
            </div>
          </div>

          <div className="flex items-center gap-1 px-3 py-1">
            <button
              onClick={() => setShowStarred(false)}
              className={`flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors ${
                !showStarred
                  ? "bg-sidebar-active text-foreground"
                  : "text-muted hover:text-foreground"
              }`}
            >
              <History size={12} />
              <span>Recent</span>
            </button>
            <button
              onClick={() => setShowStarred(true)}
              className={`flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors ${
                showStarred
                  ? "bg-sidebar-active text-foreground"
                  : "text-muted hover:text-foreground"
              }`}
            >
              <Star size={12} />
              <span>Starred</span>
            </button>
          </div>

          <nav className="flex-1 overflow-y-auto px-2 pb-2">
            {conversations.length === 0 && (
              <div className="relative border border-black/10 px-3 py-4 mt-2 corner-markers">
                <span className="cm-tl" />
                <span className="cm-tr" />
                <span className="cm-bl" />
                <span className="cm-br" />
                <p className="text-xs text-muted text-center">
                  No conversations yet
                </p>
              </div>
            )}
            {conversations.map((conv) => (
              <div
                key={conv.id}
                onClick={() => onSelectConversation(conv.id)}
                className={`group flex items-center gap-0.5 w-full px-2 py-1 rounded text-sm transition-colors cursor-pointer ${
                  conv.id === activeConversationId
                    ? "bg-sidebar-active text-foreground font-medium"
                    : "text-muted hover:bg-sidebar-hover hover:text-foreground"
                }`}
              >
                <span className="flex-1 truncate">{conv.title}</span>
                <button
                  onClick={(e) => handleToggleStar(e, conv.id)}
                  className="shrink-0 p-0.5 rounded opacity-0 group-hover:opacity-100 hover:text-amber-400 transition-opacity"
                  title={conv.starred ? "Unstar" : "Star"}
                >
                  <Star size={12} fill={conv.starred ? "currentColor" : "none"} />
                </button>
                <button
                  onClick={(e) => handleDelete(e, conv.id)}
                  className="shrink-0 p-0.5 rounded opacity-0 group-hover:opacity-100 hover:text-red-400 transition-opacity"
                  title="Delete"
                >
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
          </nav>
        </div>
      )}
    </aside>
  );
}
