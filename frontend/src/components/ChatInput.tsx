"use client";

import { useState, useRef, useCallback, DragEvent } from "react";
import { ArrowUp, Paperclip, Loader2 } from "lucide-react";

interface ChatInputProps {
  onSend: (message: string) => void;
  onAttach: (files: File[]) => void;
  uploading: boolean;
  loading: boolean;
}

export default function ChatInput({ onSend, onAttach, uploading, loading }: ChatInputProps) {
  const [value, setValue] = useState("");
  const [dragging, setDragging] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSend = () => {
    const trimmed = value.trim();
    if (!trimmed || loading || uploading) return;
    onSend(trimmed);
    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = () => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 200) + "px";
  };

  const handleFiles = useCallback((files: FileList | null) => {
    if (!files || files.length === 0 || uploading) return;
    onAttach(Array.from(files));
  }, [uploading, onAttach]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    handleFiles(e.target.files);
    e.target.value = "";
  };

  const handleDragOver = useCallback((e: DragEvent) => {
    e.preventDefault();
    setDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: DragEvent) => {
      e.preventDefault();
      setDragging(false);
      handleFiles(e.dataTransfer.files);
    },
    [uploading]
  );

  const busy = loading || uploading;

  return (
    <div className="border-t border-black/10 bg-background">
      <div className="max-w-3xl mx-auto px-4 py-3">
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`relative border rounded-lg transition-colors ${
            dragging
              ? "border-foreground bg-accent/5"
              : "border-black/20 bg-background corner-markers"
          }`}
        >
          <span className="cm-tl" />
          <span className="cm-tr" />
          <span className="cm-bl" />
          <span className="cm-br" />
          <textarea
            ref={textareaRef}
            rows={1}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onInput={handleInput}
            onKeyDown={handleKeyDown}
            placeholder={
              uploading
                ? "Uploading document(s)..."
                : "Ask about Kubernetes, or drop a PDF/DOCX/PPTX/image here..."
            }
            className="w-full resize-none bg-transparent px-4 py-3 pr-20 text-sm text-foreground placeholder-black/40 outline-none font-mono"
          />
          <div className="absolute right-2 bottom-2 flex items-center gap-1">
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".pdf,.txt,.html,.pptx,.docx,.png,.jpg,.jpeg,.tiff,.webp"
              className="hidden"
              onChange={handleFileChange}
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="p-1.5 rounded hover:bg-sidebar-hover text-muted transition-colors disabled:opacity-40"
              aria-label="Attach file"
              title="Upload a document (PDF, DOCX, PPTX, HTML, TXT, or image)"
            >
              <Paperclip size={16} />
            </button>
            <button
              onClick={handleSend}
              disabled={!value.trim() || busy}
              className="p-1.5 rounded bg-foreground text-background hover:opacity-80 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
              aria-label="Send message"
            >
              {busy ? <Loader2 size={16} className="animate-spin" /> : <ArrowUp size={16} />}
            </button>
          </div>
        </div>
        <div className="flex items-center justify-center gap-2 mt-2">
          <span className="text-xs text-muted">Model:</span>
          <span className="text-xs text-foreground font-medium">Llama 3.3 70B</span>
          <span className="text-xs text-muted">&middot;</span>
          <span className="text-xs text-muted">Kubernetes RAG</span>
          <span className="text-xs text-muted">&middot;</span>
          <span className="text-xs text-muted">Drag &amp; drop docs to index</span>
        </div>
      </div>
    </div>
  );
}
