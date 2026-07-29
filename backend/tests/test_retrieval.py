import pytest

from app.core.embeddings import embedding_manager
from app.core.qdrant_store import qdrant_manager
from app.core.reranker import reranker


@pytest.mark.eval
@pytest.mark.asyncio
class TestRetrieval:
    async def test_embed_query(self):
        vector = await embedding_manager.embed("What is a Kubernetes Pod?")
        assert vector is not None
        assert len(vector) > 0
        assert all(isinstance(v, float) for v in vector)

    async def test_qdrant_search_returns_results(self):
        vector = await embedding_manager.embed("What is a Kubernetes Pod?")
        results = await qdrant_manager.search(vector, top_k=10)
        assert len(results) > 0
        for r in results:
            assert r.payload is not None
            assert "text" in r.payload
            assert "source" in r.payload

    async def test_qdrant_search_autoscaling_query(self):
        vector = await embedding_manager.embed("How does Horizontal Pod Autoscaling work?")
        results = await qdrant_manager.search(vector, top_k=10)
        sources = [r.payload.get("source", "") for r in results]
        autoscale_files = [s for s in sources if "autoscale" in s.lower() or "pods_autoscale" in s.lower()]
        assert len(autoscale_files) > 0, (
            f"Expected autoscaling results but got sources: {sources[:5]}"
        )

    async def test_reranker_improves_ordering(self):
        query = "How do I create a CronJob?"
        vector = await embedding_manager.embed(query)
        results = await qdrant_manager.search(vector, top_k=10)
        chunks = [
            {"text": r.payload.get("text", ""), "source": r.payload.get("source", ""), "score": r.score or 0}
            for r in results
        ]
        reranked = await reranker.rerank(query, chunks, top_k=5)
        assert len(reranked) > 0
        assert reranked[0].get("score", 0) >= reranked[-1].get("score", 0)

    async def test_reranker_top_result_relevant(self):
        query = "What is Horizontal Pod Autoscaling?"
        vector = await embedding_manager.embed(query)
        results = await qdrant_manager.search(vector, top_k=10)
        chunks = [
            {"text": r.payload.get("text", ""), "source": r.payload.get("source", ""), "score": r.score or 0}
            for r in results
        ]
        reranked = await reranker.rerank(query, chunks, top_k=5)
        if reranked:
            assert reranked[0].get("score", 0) > 0.1
