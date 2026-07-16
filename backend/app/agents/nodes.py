import time

from app.agents.state import ThinkingStep
from app.agents.router import route_query
from app.core.llm import llm_manager
from app.core.prompts import load_prompt
from app.core.embeddings import embedding_manager
from app.core.qdrant_store import qdrant_manager
from app.core.reranker import reranker


async def input_guard_node(state: dict) -> dict:
    start = time.perf_counter()
    query = state["user_query"]
    system = (
        "You are a Kubernetes topic classifier. "
        "Determine if the user query is related to Kubernetes (including pods, deployments, services, "
        "clusters, nodes, containers, orchestration, kubectl, YAML manifests, etc.). "
        "Reply ONLY with PASS or REJECT."
    )
    result = await llm_manager.generate(system, query, max_tokens=100)
    passed = "pass" in result.strip().lower()
    duration = (time.perf_counter() - start) * 1000
    step = ThinkingStep(
        stage="input_guard",
        detail=f"{'passed' if passed else 'rejected'} — {result.strip()}",
        duration_ms=round(duration, 2),
    )
    return {"guardrail_input_passed": passed, "thinking_steps": [step]}


async def router_node(state: dict) -> dict:
    start = time.perf_counter()
    intent = await route_query(state["user_query"])
    duration = (time.perf_counter() - start) * 1000
    step = ThinkingStep(
        stage="router",
        detail=f"intent: {intent}",
        duration_ms=round(duration, 2),
    )
    return {"intent": intent, "thinking_steps": [step]}


async def retrieve_node(state: dict) -> dict:
    start = time.perf_counter()
    query = state["user_query"]
    vector = await embedding_manager.embed(query)
    results = await qdrant_manager.search(vector, top_k=10)
    duration = (time.perf_counter() - start) * 1000
    sources_detail = ", ".join(
        sorted(set(
            r.payload.get("source", "unknown").rsplit("/", 1)[-1]
            for r in results
        ))
    ) if results else "no matches"
    step = ThinkingStep(
        stage="retrieve",
        detail=f"retrieved {len(results)} chunks from {sources_detail}",
        duration_ms=round(duration, 2),
    )
    return {"retrieved_chunks": results, "thinking_steps": [step]}


async def rerank_node(state: dict) -> dict:
    start = time.perf_counter()
    query = state["user_query"]
    chunks = state["retrieved_chunks"]
    if not chunks:
        step = ThinkingStep(stage="rerank", detail="no chunks to rerank", duration_ms=0)
        return {"reranked_chunks": [], "thinking_steps": [step]}
    results = await reranker.rerank(query, chunks, top_k=5)
    duration = (time.perf_counter() - start) * 1000
    top_score = round(results[0].get("score", 0) * 100, 1) if results else 0
    step = ThinkingStep(
        stage="rerank",
        detail=f"top score: {top_score}% from {len(results)} chunks",
        duration_ms=round(duration, 2),
    )
    return {"reranked_chunks": results, "thinking_steps": [step]}


async def generate_node(state: dict) -> dict:
    start = time.perf_counter()
    query = state["user_query"]
    chunks = state["reranked_chunks"]

    context = ""
    sources = []
    if chunks:
        parts = []
        seen = set()
        for i, c in enumerate(chunks):
            text = c.get("text") or c.get("payload", {}).get("text", "")
            source = c.get("payload", {}).get("source", "unknown")
            score = c.get("score", 0)
            parts.append(f"[{i+1}] (from: {source}, relevance: {round(score*100, 1)}%)\n{text}")
            key = f"{source}|{c.get('payload', {}).get('chunk_index', 0)}"
            if key not in seen:
                seen.add(key)
                sources.append({"file": source, "chunk": c.get("payload", {}).get("chunk_index", 0), "score": score})
        context = "\n\n".join(parts)

    prompt = load_prompt("generation")
    system = prompt["system_prompt"]
    user_prompt = f"Context:\n{context}\n\nQuestion: {query}" if context else f"Question: {query}"

    answer = await llm_manager.generate(system, user_prompt, max_tokens=2048)

    duration = (time.perf_counter() - start) * 1000
    step = ThinkingStep(
        stage="llm",
        detail=f"@kubernetes-chatbot/llama3-70b-8192 · {round(duration, 0)}ms · {len(answer)} chars",
        duration_ms=round(duration, 2),
    )
    return {"generated_answer": answer, "sources": sources, "thinking_steps": [step]}


async def output_guard_node(state: dict) -> dict:
    start = time.perf_counter()
    answer = state["generated_answer"]
    sources = state["sources"]
    if not sources:
        step = ThinkingStep(stage="guard_output", detail="no sources to verify against", duration_ms=0)
        return {"guardrail_output_passed": True, "thinking_steps": [step]}

    system = (
        "You are a grounding checker. Given a list of source documents and an answer, "
        "check how many claims in the answer are directly supported by the sources. "
        "Reply ONLY with a fraction like '3/4' meaning 3 of 4 claims are grounded."
    )
    source_text = "\n".join(f"- {s['file']}" for s in sources)
    result = await llm_manager.generate(system, f"Sources:\n{source_text}\n\nAnswer:\n{answer}", max_tokens=100)
    grounded = result.strip()

    duration = (time.perf_counter() - start) * 1000
    step = ThinkingStep(
        stage="guard_output",
        detail=f"grounded: {grounded}",
        duration_ms=round(duration, 2),
    )
    return {"guardrail_output_passed": True, "thinking_steps": [step]}
