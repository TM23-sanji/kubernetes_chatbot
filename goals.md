# Project Goals & Roadmap

Tracking the experiments and enhancements to tackle one phase at a time.

## Known Issues

### ISSUE-001: NeonDB cold-start → `Authentication timed out` (asyncpg.ProtocolViolationError)

**Symptom:** Intermittent 500 on DB queries (e.g. `GET /api/conversations`). First requests after idle periods fail with `asyncpg.exceptions.ProtocolViolationError: Authentication timed out`.

**Root cause:** Neon serverless Postgres sleeps the compute after ~5 min of inactivity. `DatabaseManager` uses `NullPool` (postgres.py), so every session opens a brand-new connection; when the compute is waking up, it stalls during the auth handshake and asyncpg's auth timeout fires before Neon finishes booting.

**Fix plan:**
- [ ] Switch `create_async_engine` from `NullPool` to a pooled engine: `pool_size=5, max_overflow=10, pool_pre_ping=True, pool_recycle=1800` + `connect_args={"timeout": 30}` for cold-start headroom
- [ ] Add a lightweight keep-alive background task running `SELECT 1` every ~60s to keep the compute awake
- [ ] Wrap DB ops in a small retry (1 retry, ~2s backoff) for the cold-start window

## Phase 1: Ingestion & Document Management

- [x] Real document upload endpoint — replace the `/api/chat/upload` stub with `POST /api/ingest/upload` (save file → parse → clean → chunk → embed → ingest → return status)
- [x] Support upload formats: `.pdf`, `.pptx`, `.docx`, `.html`, `.txt`, plus images (`.png`, `.jpg`, `.jpeg`, `.tiff`, `.webp`) via OCR
- [x] OCR for scanned/image-based PDFs: rasterize pages with PyMuPDF, run local OCR (rapidocr-onnxruntime); pure-pip, no system deps, no API calls
- [x] Cleaning filters before chunking: alphanumeric-ratio check (drops CSS/JS/code), min word count, near-duplicate (MinHash/LSH) dedup
- [x] Incremental re-ingestion — use the per-file `checksum` to skip unchanged files and only process new/changed ones
- [x] Document listing/management API — list ingested docs, view chunk counts, delete/re-ingest a single doc
- [x] Hybrid search payload — ensure metadata (source, chunk_index, data_version) is searchable/filterable for later per-intent routing
- [x] Upload UI in the frontend (drag-and-drop docs, progress + status feedback)

**Exit criteria:** uploading a new doc (text or image/scanned PDF) makes it retrievable in a follow-up chat; re-uploading an unchanged file is skipped by checksum.

## Phase 2: Memory & Routing

## Phase 2: Memory & Routing

### Memory
- [ ] Replace naive `_load_history()` (last-2-messages as a string) with true conversation state using LangGraph `messages` + `PostgresSaver` checkpointer
- [ ] Token-budget trimming — cap context size instead of blindly appending history
- [ ] Optional: summary memory (e.g., LangMem) for long conversations

### Routing
- [ ] Use the `intent` output from `router_node` to branch behavior — currently `router → retrieve` is unconditional
- [ ] Per-intent retrieval strategy (category-filtered Qdrant search, different `top_k`, per-intent prompts)
- [ ] Fix response cache to be context-aware (conversation-scoped keys, not just content hash) so cached answers respect history

**Exit criteria:** multi-turn questions correctly reference earlier turns; the router demonstrably changes retrieval behavior per intent.

## Phase 3: Tool Calls & Agentic Behavior

- [ ] Give the LLM real tools via `bind_tools()` / `ToolNode` in a ReAct loop
- [ ] Read-only Kubernetes tools: `search_qdrant(query)`, `list_namespaces()`, `get_cluster_status()`, `get_pod_info(name)` (kubectl or K8s API, read-only)
- [ ] Guarded execution — keep input/output guardrails enforced around tool invocations
- [ ] Stream tool-call events to the frontend (thinking/action visibility)

**Exit criteria:** the agent can answer "how is my cluster doing?" by actually querying cluster state, with tool calls surfaced in the UI.

## Backlog / Ideas

- [ ] RAGAS eval on full 20-query dataset (no `RAGAS_LIMIT`)
- [ ] Clean up RAGAS deprecation warnings (`ragas.metrics` → `ragas.metrics.collections`)
- [ ] Vector store hybrid search (BM25 + dense) in Qdrant
