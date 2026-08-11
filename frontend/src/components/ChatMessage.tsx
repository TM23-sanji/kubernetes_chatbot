"use client";

import { useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  FileText,
  Brain,
  ShieldCheck,
  Route,
  Sparkles,
  Archive,
  Database,
} from "lucide-react";

interface Source {
  file: string;
  chunk: number;
  score: number;
}

interface ThinkingStep {
  stage: string;
  detail: string;
  duration_ms: number;
}

interface ChatMessageProps {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  thinking_steps?: ThinkingStep[];
}

const stageIcons: Record<string, React.ReactNode> = {
  input_guard: <ShieldCheck size={14} />,
  router: <Route size={14} />,
  retrieve: <FileText size={14} />,
  rerank: <Sparkles size={14} />,
  llm: <Brain size={14} />,
  guard_output: <ShieldCheck size={14} />,
  compaction: <Archive size={14} />,
  cache: <Database size={14} />,
};

export default function ChatMessage({
  role,
  content,
  sources,
  thinking_steps,
}: ChatMessageProps) {
  const [thinkingOpen, setThinkingOpen] = useState(false);
  const [sourcesOpen, setSourcesOpen] = useState(false);

  return (
    <div
      className={`flex ${role === "user" ? "justify-end" : "justify-start"} mb-4 animate-fade-in`}
    >
      <div
        className={`max-w-[80%] px-4 py-3 ${
          role === "user"
            ? "bg-message-bg-user text-message-user"
            : "border border-black/20 bg-background"
        } ${role === "assistant" ? "relative corner-markers" : "rounded"}`}
      >
        {role === "assistant" && (
          <>
            <span className="cm-tl" />
            <span className="cm-tr" />
            <span className="cm-bl" />
            <span className="cm-br" />
          </>
        )}
        <p className="text-sm whitespace-pre-wrap leading-relaxed">{content}</p>

        {role === "assistant" && thinking_steps && thinking_steps.length > 0 && (
          <div className="mt-3 border-t border-black/10 pt-2">
            <button
              onClick={() => setThinkingOpen(!thinkingOpen)}
              className="flex items-center gap-1.5 text-xs text-muted hover:text-foreground transition-colors"
            >
              {thinkingOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              <Brain size={14} />
              <span>Thinking trace ({thinking_steps.length} steps)</span>
            </button>
            {thinkingOpen && (
              <div className="mt-2 space-y-1.5">
                {thinking_steps.map((step, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-2 text-xs text-muted bg-sidebar rounded px-2 py-1.5"
                  >
                    {stageIcons[step.stage] || <Brain size={14} />}
                    <span className="font-medium text-foreground/80">
                      {step.stage}
                    </span>
                    <span className="flex-1">{step.detail}</span>
                    <span className="tabular-nums opacity-60">
                      {step.duration_ms.toFixed(0)}ms
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {role === "assistant" && sources && sources.length > 0 && (
          <div className="mt-2">
            <button
              onClick={() => setSourcesOpen(!sourcesOpen)}
              className="flex items-center gap-1.5 text-xs text-muted hover:text-foreground transition-colors"
            >
              {sourcesOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              <FileText size={14} />
              <span>Sources ({sources.length})</span>
            </button>
            {sourcesOpen && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {sources.map((src, i) => (
                  <span
                    key={i}
                    className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 border border-black/10 text-muted"
                  >
                    <FileText size={11} />
                    {src.file.replace(/^.*[\\/]/, "")}
                    <span className="opacity-60">({(src.score * 100).toFixed(0)}%)</span>
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
