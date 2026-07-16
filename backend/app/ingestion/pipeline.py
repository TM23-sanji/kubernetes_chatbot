import uuid
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime, timezone

from app.ingestion.parser import parse_document, SUPPORTED_EXTENSIONS
from app.ingestion.chunker import chunk_text
from app.core.embeddings import embedding_manager
from app.core.qdrant_store import qdrant_manager
from app.db.postgres import db_manager
from app.db.models import IngestionRun
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


async def run_ingestion(data_dir: str = "DATA/true_data") -> dict:
    data_path = Path(data_dir)
    if not data_path.exists():
        return {"error": f"Directory not found: {data_dir}", "run_id": None}

    files = [f for f in sorted(data_path.rglob("*")) if f.suffix.lower() in SUPPORTED_EXTENSIONS]
    data_version = _get_data_version()

    file_checksums = []
    all_points = []

    for file_path in files:
        checksum = hashlib.sha256(file_path.read_bytes()).hexdigest()
        file_checksums.append({"path": str(file_path), "checksum": checksum})

        text = parse_document(str(file_path))
        if not text.strip():
            continue

        chunks = chunk_text(text, {"source": str(file_path), "checksum": checksum})
        texts = [c["text"] for c in chunks]
        embeddings = await embedding_manager.embed_batch(texts)

        for chunk, emb in zip(chunks, embeddings):
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk["text"]))
            all_points.append({
                "id": point_id,
                "vector": emb,
                "payload": {
                    "text": chunk["text"],
                    **chunk["metadata"],
                    "data_version": data_version,
                    "ingested_at": datetime.now(timezone.utc).isoformat(),
                },
            })

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
        "total_chunks": len(all_points),
    }
