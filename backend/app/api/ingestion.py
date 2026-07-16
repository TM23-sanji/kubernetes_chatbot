from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.ingestion.pipeline import run_ingestion

router = APIRouter(prefix="/ingest", tags=["ingestion"])


class IngestResponse(BaseModel):
    run_id: str | None
    data_version: str | None
    files_processed: int
    total_chunks: int
    error: str | None = None


@router.post("")
async def ingest():
    try:
        result = await run_ingestion()
        if result.get("error"):
            raise HTTPException(status_code=400, detail=result["error"])
        return IngestResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
