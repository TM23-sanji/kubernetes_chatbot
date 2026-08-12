import hashlib
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from sqlalchemy import select

from app.ingestion.pipeline import run_ingestion, _ingest_file, _get_data_version, _lookup_checksum, _record_file
from app.ingestion.parser import SUPPORTED_EXTENSIONS
from app.core.qdrant_store import qdrant_manager
from app.db.postgres import db_manager
from app.db.models import IngestionRun, IngestedFile

router = APIRouter(prefix="/ingest", tags=["ingestion"])

UPLOAD_DIR = Path("DATA/uploads")


class IngestResponse(BaseModel):
    run_id: str | None
    data_version: str | None
    files_processed: int
    files_skipped: int = 0
    chunks_deduped: int = 0
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


class DocumentResponse(BaseModel):
    checksum: str
    filename: str
    path: str
    chunk_count: int
    data_version: str | None
    ingested_at: str | None


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

    checksum = hashlib.sha256(content).hexdigest()

    existing = await _lookup_checksum(checksum)
    if existing:
        dest.unlink(missing_ok=True)
        return UploadResponse(
            file_id=file_id,
            filename=file.filename or dest.name,
            size_bytes=size_bytes,
            content_type=file.content_type,
            checksum=checksum,
            chunk_count=existing.chunk_count or 0,
            skipped=True,
        )

    try:
        data_version = _get_data_version()
        points, text, checksum, _dropped = await _ingest_file(dest, data_version)
        if points:
            await qdrant_manager.upsert(points)
            await _record_file(checksum, dest.name, str(dest), len(points), data_version)

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
            skipped=False,
        )
    except Exception as e:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")


@router.get("/documents")
async def list_documents():
    async with await db_manager.get_session() as session:
        result = await session.execute(select(IngestedFile).order_by(IngestedFile.ingested_at.desc()))
        rows = result.scalars().all()
    return [
        DocumentResponse(
            checksum=r.checksum,
            filename=r.filename,
            path=r.path,
            chunk_count=r.chunk_count or 0,
            data_version=r.data_version,
            ingested_at=r.ingested_at.isoformat() if r.ingested_at else None,
        )
        for r in rows
    ]


@router.delete("/documents/{checksum}")
async def delete_document(checksum: str):
    async with await db_manager.get_session() as session:
        result = await session.execute(select(IngestedFile).where(IngestedFile.checksum == checksum))
        record = result.scalar_one_or_none()
        if not record:
            raise HTTPException(status_code=404, detail="Document not found")
        await session.delete(record)
        await session.commit()

    deleted = await qdrant_manager.delete_by_checksum(checksum)
    try:
        Path(record.path).unlink(missing_ok=True)
    except OSError:
        pass
    return {"checksum": checksum, "deleted_chunks": deleted}


@router.post("/documents/{checksum}/reingest")
async def reingest_document(checksum: str):
    record = await _lookup_checksum(checksum)
    if not record:
        raise HTTPException(status_code=404, detail="Document not found")

    path = Path(record.path)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Source file missing: {record.path}")

    await qdrant_manager.delete_by_checksum(checksum)

    data_version = _get_data_version()
    points, _text, _checksum, _dropped = await _ingest_file(path, data_version)
    if points:
        await qdrant_manager.upsert(points)

    async with await db_manager.get_session() as session:
        record = await session.get(IngestedFile, checksum)
        record.chunk_count = len(points)
        record.data_version = data_version
        await session.commit()

    return {"checksum": checksum, "chunk_count": len(points)}
