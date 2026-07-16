"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Braces,
  PenLine,
  BookOpen,
  GraduationCap,
  Wrench,
  CuboidIcon as Cube,
} from "lucide-react";
import Sidebar from "@/components/Sidebar";
import ChatInput from "@/components/ChatInput";
import ChatMessage from "@/components/ChatMessage";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: { file: string; chunk: number; score: number }[];
  thinking_steps?: { stage: string; detail: string; duration_ms: number }[];
}

const quickActions = [
  { icon: Braces, label: "Code", description: "Generate Kubernetes manifests" },
  { icon: Cube, label: "Debug", description: "Troubleshoot cluster issues" },
  { icon: BookOpen, label: "Explain", description: "Break down K8s concepts" },
  { icon: GraduationCap, label: "Learn", description: "Step-by-step tutorials" },
  { icon: PenLine, label: "Write", description: "Draft documentation" },
  { icon: Wrench, label: "Optimize", description: "Improve deployments" },
];

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Home() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [conversationKey, setConversationKey] = useState(0);

  const loadMessages = useCallback(async (convId: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/chat/${convId}/history`);
      if (res.ok) {
        const data = await res.json();
        setMessages(data);
      }
    } catch {
      // silent
    }
  }, []);

  useEffect(() => {
    if (activeConversationId) {
      loadMessages(activeConversationId);
    } else {
      setMessages([]);
    }
  }, [activeConversationId, loadMessages, conversationKey]);

  const handleSend = async (message: string) => {
    setLoading(true);
    const tempId = `temp-${Date.now()}`;
    setMessages((prev) => [...prev, { id: tempId, role: "user", content: message }]);

    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message,
          conversation_id: activeConversationId,
        }),
      });

      if (!res.ok) throw new Error("Chat request failed");

      const data = await res.json();
      setActiveConversationId(data.conversation_id);
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== tempId),
        {
          id: data.conversation_id + "-user",
          role: "user",
          content: message,
        },
        {
          id: data.conversation_id + "-assistant",
          role: "assistant",
          content: data.reply,
          sources: data.sources,
          thinking_steps: data.thinking_steps,
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== tempId),
        { id: "err", role: "assistant", content: "Sorry, something went wrong. Please try again." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleAttach = async (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    try {
      await fetch(`${API_BASE}/api/chat/upload`, {
        method: "POST",
        body: formData,
      });
    } catch {
      // silent
    }
  };

  const handleNewConversation = () => {
    setActiveConversationId(null);
    setMessages([]);
    setConversationKey((k) => k + 1);
  };

  const handleSelectConversation = (id: string | null) => {
    setActiveConversationId(id);
    setConversationKey((k) => k + 1);
  };

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar
        open={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
        activeConversationId={activeConversationId}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
      />
      <main className="flex-1 flex flex-col min-w-0">
        {messages.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center px-4 overflow-y-auto">
            <div className="max-w-xl w-full text-center">
              <div className="w-10 h-10 rounded-full bg-accent/10 flex items-center justify-center mx-auto mb-6">
                <Cube size={20} className="text-accent" />
              </div>
              <h1 className="text-4xl font-semibold tracking-tight text-foreground mb-3">
                How can I help you today?
              </h1>
              <p className="text-sm text-muted mb-8">
                Ask anything about Kubernetes &mdash; deploy, debug, optimize, and learn
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {quickActions.map((action) => (
                  <button
                    key={action.label}
                    onClick={() => handleSend(action.description)}
                    className="flex flex-col items-center gap-1.5 px-3 py-3 rounded-lg border border-border bg-background hover:bg-sidebar-hover transition-colors group"
                  >
                    <action.icon
                      size={18}
                      className="text-muted group-hover:text-accent transition-colors"
                    />
                    <span className="text-xs font-medium text-foreground">
                      {action.label}
                    </span>
                    <span className="text-[10px] text-muted leading-tight">
                      {action.description}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto px-4 py-6">
            <div className="max-w-3xl mx-auto">
              {messages.map((msg) => (
                <ChatMessage
                  key={msg.id}
                  role={msg.role}
                  content={msg.content}
                  sources={msg.sources}
                  thinking_steps={msg.thinking_steps}
                />
              ))}
              {loading && (
                <div className="flex justify-start mb-4">
                  <div className="max-w-[80%] rounded-2xl px-4 py-3 bg-sidebar border border-border text-foreground">
                    <p className="text-sm text-muted animate-pulse">Thinking...</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
        <ChatInput onSend={handleSend} onAttach={handleAttach} loading={loading} />
      </main>
    </div>
  );
}
