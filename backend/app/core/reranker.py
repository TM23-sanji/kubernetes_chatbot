class Reranker:
    def __init__(self):
        self.model = None

    async def initialize(self):
        from flashrank import Ranker
        self.model = Ranker(model_name="ms-marco-MiniLM-L-12-v2")

    async def rerank(self, query: str, passages: list[dict], top_k: int = 3) -> list[dict]:
        if not self.model or not passages:
            return passages[:top_k]
        flashrank_passages = []
        for i, p in enumerate(passages):
            flashrank_passages.append({
                "id": str(i),
                "text": p.get("text", p.get("payload", {}).get("text", "")),
                "meta": p,
            })
        results = self.model.rerank(query=query, passages=flashrank_passages)
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
