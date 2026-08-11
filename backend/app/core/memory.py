import asyncio

from app.config import settings


class MemoryManager:
    """Short-term conversation memory via the mem0 Platform API.

    Memories are scoped per conversation using `run_id=<conversation_id>`.
    All calls run in a thread (the client is sync) and are failure-tolerant:
    if mem0 is unavailable or misconfigured, chat keeps working without memory.
    """

    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            from mem0 import MemoryClient

            self._client = MemoryClient(api_key=settings.mem0_api_key or None)
        return self._client

    async def add_turns(self, conv_id: str, messages: list[dict]) -> dict:
        """Extract/update conversation memory from completed exchanges."""
        if not settings.memory_enabled or not messages:
            return {"results": []}
        try:
            return await asyncio.to_thread(
                self._get_client().add,
                messages,
                run_id=conv_id,
            )
        except Exception as e:
            print(f"[memory] add_turns failed for {conv_id}: {e}")
            return {"results": []}

    async def search(self, conv_id: str, query: str, top_k: int = 5) -> list[str]:
        if not settings.memory_enabled:
            return []
        try:
            result = await asyncio.to_thread(
                self._get_client().search,
                query,
                filters={"run_id": conv_id},
                top_k=top_k,
            )
            return [m["memory"] for m in result.get("results", [])]
        except Exception as e:
            print(f"[memory] search failed for {conv_id}: {e}")
            return []

    async def get_all(self, conv_id: str) -> list[dict]:
        if not settings.memory_enabled:
            return []
        try:
            result = await asyncio.to_thread(
                self._get_client().get_all,
                filters={"run_id": conv_id},
            )
            return result.get("results", [])
        except Exception as e:
            print(f"[memory] get_all failed for {conv_id}: {e}")
            return []

    async def delete_conversation(self, conv_id: str) -> None:
        if not settings.memory_enabled:
            return
        try:
            await asyncio.to_thread(
                self._get_client().delete_all,
                run_id=conv_id,
            )
        except Exception as e:
            print(f"[memory] delete failed for {conv_id}: {e}")


memory_manager = MemoryManager()
