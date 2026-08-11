import uuid
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime, timezone

from sqlalchemy import select

from app.ingestion.parser import parse_document_clean, SUPPORTED_EXTENSIONS
from app.ingestion.chunker import chunk_text
from app.ingestion.dedup import DedupFilter
from app.core.embeddings import embedding_manager
from app.core.qdrant_store import qdrant_manager
from app.db.postgres import db_manager
from app.db.models import IngestionRun, IngestedFile
from app.config import settings


def _get_data_version() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=Path(__file__).resolve().parent.parent.parent,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


async def _lookup_checksum(checksum: str) -> IngestedFile | None:
    async with await db_manager.get_session() as session:
        result = await session.execute(select(IngestedFile).where(IngestedFile.checksum == checksum))
        return result.scalar_one_or_none()


async def _record_file(checksum: str, filename: str, path: str, chunk_count: int, data_version: str) -> None:
    async with await db_manager.get_session() as session:
        session.add(IngestedFile(
            checksum=checksum,
            filename=filename,
            path=path,
            chunk_count=chunk_count,
            data_version=data_version,
        ))
        await session.commit()


async def run_ingestion(data_dir: str = "DATA/true_data") -> dict:
    data_path = Path(data_dir)
    if not data_path.exists():
        return {"error": f"Directory not found: {data_dir}", "run_id": None}

    files = [f for f in sorted(data_path.rglob("*")) if f.suffix.lower() in SUPPORTED_EXTENSIONS]
    data_version = _get_data_version()

    file_checksums = []
    all_points = []
    dedup = DedupFilter()
    files_skipped = 0
    chunks_deduped = 0

    for file_path in files:
        checksum = hashlib.sha256(file_path.read_bytes()).hexdigest()
        file_checksums.append({"path": str(file_path), "checksum": checksum})

        if await _lookup_checksum(checksum):
            files_skipped += 1
            continue

        points, text, checksum, dropped = await _ingest_file(file_path, data_version, dedup)
        chunks_deduped += dropped
        all_points.extend(points)
        if points or text.strip():
            await _record_file(checksum, file_path.name, str(file_path), len(points), data_version)

    if all_points:
        await qdrant_manager.upsert(all_points)

    run_id = str(uuid.uuid4())
    async with await db_manager.get_session() as session:
        run = IngestionRun(
            id=run_id,
            data_version=data_version,
            files_processed=file_checksums,
            chunk_count=len(all_points),
        )
        session.add(run)
        await session.commit()

    return {
        "run_id": run_id,
        "data_version": data_version,
        "files_processed": len(file_checksums),
        "files_skipped": files_skipped,
        "chunks_deduped": chunks_deduped,
        "total_chunks": len(all_points),
    }


async def _ingest_file(
    file_path: Path,
    data_version: str,
    dedup: DedupFilter | None = None,
) -> tuple[list[dict], str, str, int]:
    """Parse, clean, chunk, and embed a single file. Returns (points, text, checksum, dropped)."""
    checksum = hashlib.sha256(file_path.read_bytes()).hexdigest()
    text = parse_document_clean(str(file_path))
    if not text.strip():
        return [], text, checksum, 0

    chunks = chunk_text(text, {"source": str(file_path), "checksum": checksum})
    kept = []
    dropped = 0
    for chunk in chunks:
        if dedup is not None and dedup.is_duplicate(chunk["text"]):
            dropped += 1
            continue
        if dedup is not None:
            dedup.add(chunk["text"])
        kept.append(chunk)

    if not kept:
        return [], text, checksum, dropped

    texts = [c["text"] for c in kept]
    embeddings = await embedding_manager.embed_batch(texts)

    points = []
    for chunk, emb in zip(kept, embeddings):
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk["text"]))
        points.append({
            "id": point_id,
            "vector": emb,
            "payload": {
                "text": chunk["text"],
                **chunk["metadata"],
                "data_version": data_version,
                "ingested_at": datetime.now(timezone.utc).isoformat(),
            },
        })
    return points, text, checksum, dropped
