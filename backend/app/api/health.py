from fastapi import APIRouter

from app.config import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "memory": {
            "enabled": settings.memory_enabled and bool(settings.mem0_api_key),
            "compaction_every": settings.memory_compaction_every,
        },
    }
