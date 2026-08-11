import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from app.ingestion.pipeline import run_ingestion, _ingest_file, _get_data_version
from app.ingestion.parser import SUPPORTED_EXTENSIONS
from app.core.qdrant_store import qdrant_manager
from app.db.postgres import db_manager
from app.db.models import IngestionRun
from datetime import datetime, timezone

router = APIRouter(prefix="/ingest", tags=["ingestion"])

UPLOAD_DIR = Path("DATA/uploads")


class IngestResponse(BaseModel):
    run_id: str | None
    data_version: str | None
    files_processed: int
    total_chunks: int
    error: str | None = None


class UploadResponse(BaseModel):
    file_id: str
    filename: str
    size_bytes: int
    content_type: str | None
    checksum: str
    chunk_count: int
    skipped: bool = False
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


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{ext}'. Supported: {sorted(SUPPORTED_EXTENSIONS)}",
        )

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_id = str(uuid.uuid4())
    dest = UPLOAD_DIR / f"{file_id}_{Path(file.filename).name}"

    content = await file.read()
    dest.write_bytes(content)
    size_bytes = len(content)

    if size_bytes == 0:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    try:
        data_version = _get_data_version()
        points, text, checksum = await _ingest_file(dest, data_version)
        skipped = len(points) == 0 and text.strip() == ""
        if points:
            await qdrant_manager.upsert(points)

        async with await db_manager.get_session() as session:
            run = IngestionRun(
                id=str(uuid.uuid4()),
                data_version=data_version,
                files_processed=[{"path": str(dest), "checksum": checksum}],
                chunk_count=len(points),
            )
            session.add(run)
            await session.commit()

        return UploadResponse(
            file_id=file_id,
            filename=file.filename or dest.name,
            size_bytes=size_bytes,
            content_type=file.content_type,
            checksum=checksum,
            chunk_count=len(points),
            skipped=skipped,
        )
    except Exception as e:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")
