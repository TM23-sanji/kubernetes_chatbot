from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import db_manager
from app.db import repository as repo
from app.core.memory import memory_manager

router = APIRouter(prefix="/conversations", tags=["conversations"])


async def get_session():
    async with await db_manager.get_session() as session:
        yield session


@router.post("")
async def create_conversation(session: AsyncSession = Depends(get_session)):
    conv = await repo.create_conversation(session)
    return {"id": conv.id, "title": conv.title, "created_at": conv.created_at.isoformat() if conv.created_at else None}


@router.get("")
async def list_conversations(
    q: str | None = Query(None),
    filter: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
):
    convs = await repo.list_conversations(session, search=q, filter=filter)
    return [
        {
            "id": c.id,
            "title": c.title,
            "starred": c.starred,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }
        for c in convs
    ]


@router.get("/{conv_id}")
async def get_conversation(conv_id: str, session: AsyncSession = Depends(get_session)):
    conv = await repo.get_conversation(session, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"id": conv.id, "title": conv.title, "starred": conv.starred, "created_at": conv.created_at.isoformat() if conv.created_at else None}


@router.delete("/{conv_id}")
async def delete_conversation(conv_id: str, session: AsyncSession = Depends(get_session)):
    deleted = await repo.delete_conversation(session, conv_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await memory_manager.delete_conversation(conv_id)
    return {"ok": True}


@router.post("/{conv_id}/star")
async def toggle_star(conv_id: str, session: AsyncSession = Depends(get_session)):
    conv = await repo.toggle_star_conversation(session, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"id": conv.id, "starred": conv.starred}
