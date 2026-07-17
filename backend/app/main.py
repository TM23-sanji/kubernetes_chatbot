import os
from contextlib import asynccontextmanager

import logfire
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.chat import router as chat_router
from app.api.ingestion import router as ingestion_router
from app.api.conversations import router as conversations_router
from app.core.embeddings import embedding_manager
from app.core.qdrant_store import qdrant_manager
from app.core.llm import llm_manager
from app.core.reranker import reranker
from app.db.postgres import db_manager
from app.db.redis import redis_manager
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.logfire_token:
        logfire.configure(
            token=settings.logfire_token,
            service_name="kubernetes-rag-chatbot",
        )
        logfire.instrument_fastapi(app)
        logfire.instrument_openai()
        logfire.instrument_httpx()
        logfire.instrument_asyncpg()
    if settings.langsmith_api_key:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGCHAIN_ENDPOINT"] = settings.langsmith_endpoint
        os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project

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


app = FastAPI(
    title="Kubernetes RAG Chatbot API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api", tags=["health"])
app.include_router(chat_router, prefix="/api", tags=["chat"])
app.include_router(ingestion_router, prefix="/api", tags=["ingestion"])
app.include_router(conversations_router, prefix="/api", tags=["conversations"])
