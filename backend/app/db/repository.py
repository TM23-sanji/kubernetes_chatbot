import uuid
from datetime import datetime, timezone
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Conversation, Message


async def create_conversation(session: AsyncSession, title: str = "New conversation") -> Conversation:
    conv = Conversation(id=str(uuid.uuid4()), title=title)
    session.add(conv)
    await session.commit()
    await session.refresh(conv)
    return conv


async def list_conversations(
    session: AsyncSession,
    search: str | None = None,
    filter: str | None = None,
) -> list[Conversation]:
    stmt = select(Conversation)
    if filter == "starred":
        stmt = stmt.where(Conversation.starred.is_(True))
    if search:
        stmt = stmt.where(Conversation.title.ilike(f"%{search}%"))
    stmt = stmt.order_by(desc(Conversation.updated_at))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_conversation(session: AsyncSession, conv_id: str) -> Conversation | None:
    return await session.get(Conversation, conv_id)


async def delete_conversation(session: AsyncSession, conv_id: str) -> bool:
    conv = await session.get(Conversation, conv_id)
    if not conv:
        return False
    await session.delete(conv)
    await session.commit()
    return True


async def toggle_star_conversation(session: AsyncSession, conv_id: str) -> Conversation | None:
    conv = await session.get(Conversation, conv_id)
    if not conv:
        return None
    conv.starred = not conv.starred
    await session.commit()
    await session.refresh(conv)
    return conv


async def add_message(
    session: AsyncSession,
    conversation_id: str,
    role: str,
    content: str,
    sources: list | None = None,
    thinking_steps: list | None = None,
) -> Message:
    msg = Message(
        id=str(uuid.uuid4()),
        conversation_id=conversation_id,
        role=role,
        content=content,
        sources=sources,
        thinking_steps=thinking_steps,
    )
    session.add(msg)

    conv = await session.get(Conversation, conversation_id)
    if conv:
        conv.updated_at = datetime.now(timezone.utc)
        if role == "user" and conv.title == "New conversation":
            conv.title = content[:80] + ("..." if len(content) > 80 else "")

    await session.commit()
    await session.refresh(msg)
    return msg


async def get_messages(session: AsyncSession, conversation_id: str) -> list[Message]:
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
