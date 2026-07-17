import hashlib
import json
import uuid

import logfire
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import agent_graph
from app.db.postgres import db_manager
from app.db import repository as repo
from app.db.redis import redis_manager

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
        }

        result = await agent_graph.ainvoke(initial_state)

        reply = result.get("generated_answer", "")
        sources = result.get("sources", [])
        thinking = result.get("thinking_steps", [])

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


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    return {
        "file_id": str(uuid.uuid4()),
        "filename": file.filename,
        "type": file.content_type,
        "preview": None,
    }


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
