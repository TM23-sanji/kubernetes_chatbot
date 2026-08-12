import asyncio
import time

from app.config import settings


class QdrantManager:
    COLLECTION_NAME = "kubernetes_docs"

    def __init__(self):
        self.client = None

    VECTOR_SIZE = 3072

    async def initialize(self):
        from qdrant_client import QdrantClient
        from qdrant_client.http.models import Distance, VectorParams, PayloadSchemaType

        self.client = QdrantClient(
            url=settings.qdrant_cluster_endpoint,
            api_key=settings.qdrant_api_key,
            timeout=120,
        )
        collections = self.client.get_collections().collections
        exists = any(c.name == self.COLLECTION_NAME for c in collections)
        if not exists:
            self.client.create_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config=VectorParams(size=self.VECTOR_SIZE, distance=Distance.COSINE),
            )
        try:
            self.client.create_payload_index(
                collection_name=self.COLLECTION_NAME,
                field_name="checksum",
                field_schema=PayloadSchemaType.KEYWORD,
            )
        except Exception:
            pass  # index already exists

    async def search(self, vector: list[float], top_k: int = 5) -> list:
        t0 = time.perf_counter()
        result = await asyncio.to_thread(
            self.client.query_points,
            collection_name=self.COLLECTION_NAME,
            query=vector,
            limit=top_k,
        )
        dur = (time.perf_counter() - t0) * 1000
        print(f"[perf] Qdrant search: {dur:.0f}ms ({len(result.points)} results)")
        return result.points

    async def upsert(self, points: list[dict], batch_size: int = 50):
        from qdrant_client.http.models import PointStruct

        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            point_structs = [
                PointStruct(
                    id=p["id"],
                    vector=p["vector"],
                    payload=p.get("payload", {}),
                )
                for p in batch
            ]
            await asyncio.to_thread(
                self.client.upsert,
                collection_name=self.COLLECTION_NAME,
                points=point_structs,
            )
            print(f"  Uploaded batch {i // batch_size + 1}/{(len(points) - 1) // batch_size + 1} ({len(batch)} points)")

    async def delete_by_checksum(self, checksum: str) -> int:
        from qdrant_client.http.models import FieldCondition, MatchValue, Filter

        matches, _ = await asyncio.to_thread(
            self.client.scroll,
            collection_name=self.COLLECTION_NAME,
            scroll_filter=Filter(
                must=[FieldCondition(key="checksum", match=MatchValue(value=checksum))]
            ),
            limit=10000,
            with_payload=False,
        )
        ids = [p.id for p in matches]
        if ids:
            await asyncio.to_thread(
                self.client.delete,
                collection_name=self.COLLECTION_NAME,
                points_selector=ids,
            )
        return len(ids)

    async def close(self):
        if self.client:
            self.client.close()


qdrant_manager = QdrantManager()
