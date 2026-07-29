import json
import os
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from app.config import settings


def load_json(filename: str) -> list[dict]:
    path = Path(__file__).parent / "data" / filename
    with open(path) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def test_queries():
    return load_json("test_queries.json")


@pytest.fixture(scope="session")
def guard_cases():
    return load_json("guard_cases.json")


@pytest.fixture(scope="session")
def eval_llm():
    from langchain_openai import ChatOpenAI
    from portkey_ai import PORTKEY_GATEWAY_URL
    return ChatOpenAI(
        model="@kubernetes-chatbot/llama-3.3-70b-versatile",
        base_url=PORTKEY_GATEWAY_URL,
        api_key=settings.portkey_api_key,
        temperature=0,
    )


@pytest.fixture(scope="session")
def event_loop():
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def setup_services():
    from app.db.postgres import db_manager
    from app.db.redis import redis_manager
    from app.core.llm import llm_manager
    from app.core.embeddings import embedding_manager
    from app.core.qdrant_store import qdrant_manager
    from app.core.reranker import reranker

    await db_manager.initialize()
    await redis_manager.initialize()
    await qdrant_manager.initialize()
    await embedding_manager.initialize()
    await llm_manager.initialize()
    await reranker.initialize()
    yield
    await db_manager.close()
    await redis_manager.close()
    await qdrant_manager.close()
    await embedding_manager.close()
    await llm_manager.close()
    await reranker.close()
