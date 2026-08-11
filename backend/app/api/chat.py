import hashlib
import json

import logfire
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import agent_graph
from app.db.postgres import db_manager
from app.db import repository as repo
from app.db.redis import redis_manager


def sse_event(event_type: str, data: object) -> str:
    return f"data: {json.dumps({event_type: data}, default=str)}\n\n"


async def _load_history(session: AsyncSession, conv_id: str) -> str:
    msgs = await repo.get_messages(session, conv_id)
    prev = msgs[:-1]
    recent = prev[-2:]
    if not recent:
        return ""
    lines = []
    for m in recent:
        role = "User" if m.role == "user" else "Assistant"
        lines.append(f"{role}: {m.content}")
    return "\n".join(lines)


router = APIRouter(prefix="/chat", tags=["chat"])


async def get_session():
    async with await db_manager.get_session() as session:
        yield session


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    sources: list
    thinking_steps: list
    conversation_id: str


@router.post("")
async def chat(req: ChatRequest, session: AsyncSession = Depends(get_session)):
    conv_id = req.conversation_id

    if not conv_id:
        conv = await repo.create_conversation(session)
        conv_id = conv.id
    else:
        conv = await repo.get_conversation(session, conv_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

    await repo.add_message(session, conv_id, "user", req.message)

    query_hash = hashlib.sha256(req.message.encode()).hexdigest()
    cache_key = f"response:{query_hash}"
    try:
        cached = await redis_manager.get(cache_key)
        if cached:
            cached_data = json.loads(cached)
            reply = cached_data["reply"]
            sources = cached_data["sources"]
            thinking = cached_data["thinking_steps"] + [
                {"stage": "cache", "detail": "full response cache hit — skipped all LLM calls", "duration_ms": 0}
            ]
            logfire.info("response cache hit", query_hash=query_hash, conv_id=conv_id)
        else:
            raise ValueError("miss")
    except Exception:
        cached = None

    if not cached:
        history = await _load_history(session, conv_id)
        initial_state = {
            "user_query": req.message,
            "messages": [],
            "intent": "",
            "retrieved_chunks": [],
            "reranked_chunks": [],
            "generated_answer": "",
            "sources": [],
            "thinking_steps": [],
            "guardrail_input_passed": True,
            "guardrail_output_passed": True,
            "conversation_history": history,
        }

        result = await agent_graph.ainvoke(initial_state)

        reply = result.get("generated_answer", "")
        sources = result.get("sources", [])
        thinking = result.get("thinking_steps", [])

        if result.get("guardrail_input_passed", True):
            try:
                await redis_manager.set(
                    cache_key,
                    json.dumps({"reply": reply, "sources": sources, "thinking_steps": thinking}, default=str),
                    ttl=86400,
                )
            except Exception:
                pass

    await repo.add_message(session, conv_id, "assistant", reply, sources=sources, thinking_steps=thinking)

    return ChatResponse(
        reply=reply,
        sources=sources,
        thinking_steps=thinking,
        conversation_id=conv_id,
    )


def _extract_chunk_content(chunk) -> str:
    if isinstance(chunk, dict):
        return chunk.get("content", "") or ""
    return getattr(chunk, "content", "") or ""


NODE_NAMES = {"input_guard", "router", "retrieve", "rerank", "generate", "output_guard", "reject"}


@router.post("/stream")
async def chat_stream(req: ChatRequest, session: AsyncSession = Depends(get_session)):
    conv_id = req.conversation_id
    if not conv_id:
        conv = await repo.create_conversation(session)
        conv_id = conv.id
    else:
        conv = await repo.get_conversation(session, conv_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
    await repo.add_message(session, conv_id, "user", req.message)

    query_hash = hashlib.sha256(req.message.encode()).hexdigest()
    cache_key = f"response:{query_hash}"
    cached_data = None
    try:
        raw = await redis_manager.get(cache_key)
        if raw:
            cached_data = json.loads(raw)
            logfire.info("response cache hit", query_hash=query_hash, conv_id=conv_id)
    except Exception:
        pass

    history = await _load_history(session, conv_id)
    initial_state: dict = {
        "user_query": req.message,
        "messages": [],
        "intent": "",
        "retrieved_chunks": [],
        "reranked_chunks": [],
        "generated_answer": "",
        "sources": [],
        "thinking_steps": [],
        "guardrail_input_passed": True,
        "guardrail_output_passed": True,
        "conversation_history": history,
    }

    async def event_generator():
        if cached_data:
            steps = cached_data["thinking_steps"] + [
                {"stage": "cache", "detail": "full response cache hit — skipped all LLM calls", "duration_ms": 0}
            ]
            yield sse_event("done", {
                "reply": cached_data["reply"],
                "sources": cached_data["sources"],
                "thinking_steps": steps,
                "conversation_id": conv_id,
            })
            async with await db_manager.get_session() as inner_session:
                await repo.add_message(
                    inner_session, conv_id, "assistant",
                    cached_data["reply"],
                    sources=cached_data["sources"],
                    thinking_steps=steps,
                )
            return

        final_state: dict = {}
        try:
            async for event in agent_graph.astream_events(initial_state, version="v2"):
                kind = event["event"]
                name = event.get("name", "")

                if kind == "on_chain_end" and name in NODE_NAMES:
                    output = event.get("data", {}).get("output", {})
                    if isinstance(output, dict):
                        steps = output.get("thinking_steps", [])
                        if steps:
                            yield sse_event("thinking", steps[-1])
                        final_state.update(output)

                elif kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk", {})
                    content = _extract_chunk_content(chunk)
                    if content:
                        yield sse_event("token", {"text": content})
        except Exception as exc:
            yield sse_event("error", {"detail": str(exc)})
            return

        yield sse_event("done", {
            "reply": final_state.get("generated_answer", ""),
            "sources": final_state.get("sources", []),
            "thinking_steps": final_state.get("thinking_steps", []),
            "conversation_id": conv_id,
        })

        async with await db_manager.get_session() as inner_session:
            if final_state.get("guardrail_input_passed", True):
                try:
                    await redis_manager.set(
                        cache_key,
                        json.dumps({
                            "reply": final_state.get("generated_answer", ""),
                            "sources": final_state.get("sources", []),
                            "thinking_steps": final_state.get("thinking_steps", []),
                        }, default=str),
                        ttl=86400,
                    )
                except Exception:
                    pass

            await repo.add_message(
                inner_session, conv_id, "assistant",
                final_state.get("generated_answer", ""),
                sources=final_state.get("sources", []),
                thinking_steps=final_state.get("thinking_steps", []),
            )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/{conv_id}/history")
async def get_history(conv_id: str, session: AsyncSession = Depends(get_session)):
    conv = await repo.get_conversation(session, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    messages = await repo.get_messages(session, conv_id)
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "sources": m.sources,
            "thinking_steps": m.thinking_steps,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages
    ]
