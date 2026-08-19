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
import MemorySidebar from "@/components/MemorySidebar";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: { file: string; chunk: number; score: number }[];
  thinking_steps?: { stage: string; detail: string; duration_ms: number }[];
}

interface MemoryItem {
  id: string;
  memory: string;
  category: string | null;
  score: number | null;
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
  const [memoryOpen, setMemoryOpen] = useState(true);
  const [memories, setMemories] = useState<MemoryItem[]>([]);
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

  const loadMemory = useCallback(async (convId: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/chat/${convId}/memory`);
      if (res.ok) {
        setMemories(await res.json());
      }
    } catch {
      // silent
    }
  }, []);

  useEffect(() => {
    if (!activeConversationId) return;
    void (async () => {
      await loadMessages(activeConversationId);
      await loadMemory(activeConversationId);
    })();
  }, [activeConversationId, loadMessages, loadMemory, conversationKey]);

  const handleSend = async (message: string) => {
    setLoading(true);
    const userTs = crypto.randomUUID();
    const tempUserId = `user-${userTs}`;
    const assistantId = `stream-${userTs}`;
    setMessages((prev) => [
      ...prev,
      { id: tempUserId, role: "user", content: message },
      { id: assistantId, role: "assistant", content: "", thinking_steps: [] },
    ]);

    try {
      const res = await fetch(`${API_BASE}/api/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, conversation_id: activeConversationId }),
      });

      if (!res.ok) throw new Error("Chat request failed");

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const block of lines) {
          const line = block.trim();
          if (!line || !line.startsWith("data: ")) continue;
          try {
            const parsed = JSON.parse(line.slice(6));

            if (parsed.thinking) {
              const step = parsed.thinking;
              setMessages((prev) => {
                const updated = [...prev];
                const idx = updated.findIndex((m) => m.id === assistantId);
                if (idx === -1) return prev;
                updated[idx] = {
                  ...updated[idx],
                  thinking_steps: [...(updated[idx].thinking_steps || []), step],
                };
                return updated;
              });
            } else if (parsed.token) {
              const text = parsed.token.text;
              setMessages((prev) => {
                const updated = [...prev];
                const idx = updated.findIndex((m) => m.id === assistantId);
                if (idx === -1) return prev;
                updated[idx] = { ...updated[idx], content: updated[idx].content + text };
                return updated;
              });
            } else if (parsed.done) {
              const d = parsed.done;
              setActiveConversationId(d.conversation_id);
              loadMemory(d.conversation_id);
              setMessages((prev) => {
                const updated = [...prev];
                const idx = updated.findIndex((m) => m.id === assistantId);
                if (idx === -1) return prev;
                updated[idx] = {
                  id: assistantId,
                  role: "assistant",
                  content: d.reply,
                  sources: d.sources,
                  thinking_steps: d.thinking_steps,
                };
                return updated;
              });
            } else if (parsed.error) {
              const detail = parsed.error.detail || "Something went wrong";
              setMessages((prev) => {
                const updated = [...prev];
                const idx = updated.findIndex((m) => m.id === assistantId);
                if (idx === -1) return prev;
                updated[idx] = {
                  id: assistantId,
                  role: "assistant",
                  content: `Sorry, something went wrong: ${detail}`,
                };
                return updated;
              });
            }
          } catch {
            // skip malformed JSON
          }
        }
      }
    } catch {
      setMessages((prev) => [
        ...prev.filter((m) => m.id !== assistantId && m.id !== tempUserId),
        { id: "err", role: "assistant", content: "Sorry, something went wrong. Please try again." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleAttach = async (files: File[]) => {
    setLoading(true);
    const userTs = Date.now();
    const tempId = `upload-${userTs}`;
    setMessages((prev) => [
      ...prev,
      { id: tempId, role: "user", content: `Uploading ${files.length} document(s)...` },
    ]);

    try {
      for (const file of files) {
        const formData = new FormData();
        formData.append("file", file);
        const res = await fetch(`${API_BASE}/api/ingest/upload`, {
          method: "POST",
          body: formData,
        });
        if (!res.ok) {
          let detail = `Upload failed (${res.status})`;
          try {
            const err = await res.json();
            if (err.detail) detail = typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail);
          } catch {
            // ignore
          }
          throw new Error(detail);
        }
        const data = await res.json();
        const suffix = data.skipped
          ? " (empty content — nothing indexed)"
          : ` — ${data.chunk_count} chunk(s) indexed`;
        setMessages((prev) => [
          ...prev,
          {
            id: `uploaded-${data.file_id}`,
            role: "assistant",
            content: `Indexed \`${file.name}\`${suffix}`,
          },
        ]);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Upload failed";
      setMessages((prev) => [
        ...prev,
        { id: `upload-err-${Date.now()}`, role: "assistant", content: msg },
      ]);
    } finally {
      setMessages((prev) => prev.filter((m) => m.id !== tempId));
      setLoading(false);
    }
  };

  const handleNewConversation = () => {
    setActiveConversationId(null);
    setMessages([]);
    setMemories([]);
    setConversationKey((k) => k + 1);
  };

  const handleSelectConversation = (id: string | null) => {
    setActiveConversationId(id);
    if (id === null) setMemories([]);
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
              <div className="w-10 h-10 rounded-full bg-accent/5 flex items-center justify-center mx-auto mb-6 border border-black/10">
                <Cube size={20} className="text-accent" />
              </div>
              <h1 className="text-4xl font-semibold tracking-tight text-foreground mb-3">
                How can I help you today?
              </h1>
              <p className="text-sm text-muted mb-8">
                Ask anything about Kubernetes &mdash; deploy, debug, optimize, and learn
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {quickActions.map((action) => (
                  <button
                    key={action.label}
                    onClick={() => handleSend(action.description)}
                    className="relative flex flex-col items-center gap-1.5 px-3 py-3 border border-black/20 bg-background hover:bg-sidebar-hover transition-colors group corner-markers"
                  >
                    <span className="cm-tl" />
                    <span className="cm-tr" />
                    <span className="cm-bl" />
                    <span className="cm-br" />
                    <action.icon
                      size={18}
                      className="text-muted group-hover:text-foreground transition-colors"
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

            </div>
          </div>
        )}
        <ChatInput onSend={handleSend} onAttach={handleAttach} uploading={loading} loading={loading} />
      </main>
      <MemorySidebar
        open={memoryOpen}
        onToggle={() => setMemoryOpen(!memoryOpen)}
        memories={memories}
      />
    </div>
  );
}
