import re
import time

from langchain_core.messages import SystemMessage, HumanMessage

from app.agents.state import ThinkingStep
from app.agents.router import route_query
from app.core.llm import llm_manager
from app.core.prompts import load_prompt
from app.core.embeddings import embedding_manager
from app.core.qdrant_store import qdrant_manager
from app.core.reranker import reranker

CANNED_REJECT = (
    "I can only answer questions related to Kubernetes. "
    "Please ask about pods, deployments, services, clusters, nodes, "
    "containers, orchestration, kubectl, YAML manifests, or similar topics."
)


async def input_guard_node(state: dict) -> dict:
    start = time.perf_counter()
    query = state["user_query"]
    system = (
        "You are a safety and Kubernetes topic classifier. "
        "Determine if the user query is (1) safe and not harmful, and "
        "(2) related to Kubernetes (including pods, deployments, services, "
        "clusters, nodes, containers, orchestration, kubectl, YAML manifests, etc.). "
        "Reply ONLY with PASS or REJECT."
    )
    result = await llm_manager.generate_guard(system, query, max_tokens=100)
    passed = "pass" in result.strip().lower()
    duration = (time.perf_counter() - start) * 1000
    step = ThinkingStep(
        stage="input_guard",
        detail=f"{'passed' if passed else 'rejected'} — {result.strip()}",
        duration_ms=round(duration, 2),
    )
    return {"guardrail_input_passed": passed, "thinking_steps": [step]}


async def reject_node(state: dict) -> dict:
    start = time.perf_counter()
    step = ThinkingStep(
        stage="reject",
        detail="query rejected by input guard — returned canned response",
        duration_ms=0,
    )
    return {
        "generated_answer": CANNED_REJECT,
        "sources": [],
        "reranked_chunks": [],
        "thinking_steps": [step],
    }


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
    t_overall = time.perf_counter()
    query = state["user_query"]

    t0 = time.perf_counter()
    vector = await embedding_manager.embed(query)
    embed_time = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    results = await qdrant_manager.search(vector, top_k=10)
    search_time = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    sources_detail = ", ".join(
        sorted(set(
            r.payload.get("source", "unknown").rsplit("/", 1)[-1]
            for r in results
        ))
    ) if results else "no matches"
    payload_time = (time.perf_counter() - t0) * 1000

    duration = (time.perf_counter() - t_overall) * 1000
    print(f"[perf] retrieve.embed: {embed_time:.0f}ms | retrieve.search: {search_time:.0f}ms | retrieve.payload: {payload_time:.0f}ms | total: {duration:.0f}ms")
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
    print(f"[perf] rerank: {duration:.0f}ms ({len(results)} chunks)")
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

    t0 = time.perf_counter()
    context = ""
    sources = []
    if chunks:
        parts = []
        seen = set()
        for i, c in enumerate(chunks):
            text = c.get("text") or ""
            source = c.get("source", "unknown")
            score_val = float(c.get("score", 0))
            parts.append(f"[{i+1}] (from: {source}, relevance: {round(score_val*100, 1)}%)\n{text}")
            key = f"{source}|{c.get('chunk_index', 0)}"
            if key not in seen:
                seen.add(key)
                sources.append({"file": source, "chunk": c.get("chunk_index", 0), "score": score_val})
        context = "\n\n".join(parts)
    format_time = (time.perf_counter() - t0) * 1000

    prompt = load_prompt("generation")
    system = prompt["system_prompt"]
    parts = []
    if context:
        parts.append(f"Context:\n{context}")
    historical = state.get("conversation_history", "")
    if historical:
        parts.append(f"Conversation history:\n{historical}")
    parts.append(f"Current Question: {query}")
    user_prompt = "\n\n".join(parts)

    t0 = time.perf_counter()
    response = await llm_manager.chat_model.ainvoke([
        SystemMessage(content=system),
        HumanMessage(content=user_prompt),
    ])
    answer = response.content
    llm_time = (time.perf_counter() - t0) * 1000

    duration = (time.perf_counter() - start) * 1000
    print(f"[perf] generate.format: {format_time:.0f}ms | generate.llm: {llm_time:.0f}ms | total: {duration:.0f}ms")
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
    result = await llm_manager.generate_guard(
        system,
        f"Sources:\n{source_text}\n\nAnswer:\n{answer}",
        max_tokens=100,
    )
    grounded = result.strip()

    ratio = 1.0
    match = re.search(r"(\d+)\s*/\s*(\d+)", grounded)
    if match:
        num, den = int(match.group(1)), int(match.group(2))
        ratio = num / den if den > 0 else 1.0

    passed = ratio >= 0.5
    if ratio < 0.5:
        warning = (
            "⚠️ **Warning**: Most claims in this answer could not be verified "
            "against the source documents. Verify critical information independently."
        )
        answer = f"{warning}\n\n{answer}"

    duration = (time.perf_counter() - start) * 1000
    step = ThinkingStep(
        stage="guard_output",
        detail=f"grounded: {grounded} (ratio: {ratio:.0%}, passed: {passed})",
        duration_ms=round(duration, 2),
    )
    return {"generated_answer": answer, "guardrail_output_passed": passed, "thinking_steps": [step]}
