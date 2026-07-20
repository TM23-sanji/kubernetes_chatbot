import asyncio
import time
from google import genai
from google.genai import errors

from app.config import settings


class EmbeddingManager:
    def __init__(self):
        self.client = None

    async def initialize(self):
        self.client = genai.Client(api_key=settings.gemini_api_key)

    async def _call_with_retry(self, texts: list[str]) -> list[list[float]]:
        for attempt in range(5):
            t0 = time.perf_counter()
            try:
                result = self.client.models.embed_content(
                    model="models/gemini-embedding-001",
                    contents=texts,
                )
                dur = (time.perf_counter() - t0) * 1000
                print(f"[perf] embedding API call: {dur:.0f}ms (attempt {attempt+1})")
                return [e.values for e in result.embeddings]
            except errors.ClientError as e:
                if "RESOURCE_EXHAUSTED" in str(e):
                    wait = 30 + (attempt * 5)
                    print(f"  Rate limited, retrying in {wait}s...")
                    await asyncio.sleep(wait)
                    continue
                raise
        raise RuntimeError("Max retries exceeded for embedding")

    async def embed(self, text: str) -> list[float]:
        t0 = time.perf_counter()
        results = await self._call_with_retry([text])
        dur = (time.perf_counter() - t0) * 1000
        print(f"[perf] embed total: {dur:.0f}ms")
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        batch_size = 10
        all_results = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            results = await self._call_with_retry(batch)
            all_results.extend(results)
        return all_results

    async def close(self):
        self.client = None


embedding_manager = EmbeddingManager()
