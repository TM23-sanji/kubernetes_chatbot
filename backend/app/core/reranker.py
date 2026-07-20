from flashrank import RerankRequest

class Reranker:
    def __init__(self):
        self.model = None

    async def initialize(self):
        from flashrank import Ranker, RerankRequest
        self.model = Ranker(model_name="ms-marco-TinyBERT-L-2-v2")

    async def rerank(self, query: str, passages: list[dict], top_k: int = 3) -> list[dict]:
        # Normalize ScoredPoint objects (from Qdrant) to plain dicts
        normalized = []
        for p in passages:
            if hasattr(p, 'payload'):
                normalized.append({**p.payload, "score": p.score, "id": p.id})
            else:
                normalized.append(p)
        passages = normalized

        if not self.model or not passages:
            return passages[:top_k]
        flashrank_passages = []
        for i, p in enumerate(passages):
            flashrank_passages.append({
                "id": str(i),
                "text": p.get("text", p.get("payload", {}).get("text", "")),
                "meta": p,
            })
        request = RerankRequest(query=query, passages=flashrank_passages)
        results = self.model.rerank(request)

        scored = []
        for r in results:
            idx = int(r["id"])
            scored.append({
                **passages[idx],
                "score": r["score"],
            })
        return scored[:top_k]

    async def close(self):
        self.model = None


reranker = Reranker()
