"use client";

import { Brain, PanelRightClose, PanelRightOpen } from "lucide-react";

interface MemoryItem {
  id: string;
  memory: string;
  category: string | null;
  score: number | null;
}

interface MemorySidebarProps {
  open: boolean;
  onToggle: () => void;
  memories: MemoryItem[];
}

export default function MemorySidebar({ open, onToggle, memories }: MemorySidebarProps) {
  return (
    <aside
      className={`relative flex-shrink-0 bg-sidebar border-l border-black/10 transition-all duration-200 ease-in-out flex flex-col ${
        open ? "w-72" : "w-12"
      }`}
    >
      <div className="flex items-center justify-between p-2 h-12 border-b border-black/10">
        {open && (
          <span className="text-sm font-medium text-foreground ml-1 flex items-center gap-1.5">
            <Brain size={14} />
            Memory
          </span>
        )}
        <button
          onClick={onToggle}
          className="p-1.5 rounded hover:bg-sidebar-hover text-muted transition-colors"
          aria-label={open ? "Close memory panel" : "Open memory panel"}
        >
          {open ? <PanelRightClose size={16} /> : <PanelRightOpen size={16} />}
        </button>
      </div>

      {open && (
        <div className="flex-1 overflow-y-auto px-3 py-3">
          {memories.length === 0 ? (
            <p className="text-xs text-muted text-center mt-8 leading-relaxed">
              No memories yet.
              <br />
              Facts are extracted from the conversation after a few turns.
            </p>
          ) : (
            <ul className="space-y-2">
              {memories.map((m) => (
                <li
                  key={m.id || m.memory}
                  className="border border-black/10 bg-background px-3 py-2"
                >
                  <p className="text-xs text-foreground leading-relaxed">{m.memory}</p>
                  <div className="mt-1.5 flex items-center gap-2">
                    {m.category && (
                      <span className="text-[10px] px-1.5 py-0.5 bg-accent/10 text-accent border border-black/10">
                        {m.category}
                      </span>
                    )}
                    {typeof m.score === "number" && (
                      <span className="text-[10px] text-muted tabular-nums">
                        {(m.score * 100).toFixed(0)}%
                      </span>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </aside>
  );
}
