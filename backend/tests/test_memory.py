import pytest

from app.api.chat import _needs_compaction, _turn_count
from app.config import settings
from app.core.memory import memory_manager


class _Msg:
    def __init__(self, role: str):
        self.role = role
        self.content = "x"


class _FakeClient:
    def __init__(self, results=None, raise_on=None):
        self._results = results or []
        self._raise_on = raise_on
        self.add_calls = []
        self.delete_calls = []

    def add(self, messages, run_id=None):
        if self._raise_on == "add":
            raise RuntimeError("mem0 down")
        self.add_calls.append((messages, run_id))
        return {"results": [{"memory": "extracted fact"}]}

    def search(self, query, filters=None, top_k=5):
        if self._raise_on == "search":
            raise RuntimeError("mem0 down")
        return {"results": [{"memory": r} for r in self._results]}

    def get_all(self, filters=None):
        if self._raise_on == "get_all":
            raise RuntimeError("mem0 down")
        return {"results": [{"memory": r} for r in self._results]}

    def delete_all(self, run_id=None):
        if self._raise_on == "delete_all":
            raise RuntimeError("mem0 down")
        self.delete_calls.append(run_id)


def _conv(users: int, extra_assistant: int = 0) -> list:
    msgs = [_Msg("user") for _ in range(users)]
    msgs += [_Msg("assistant") for _ in range(extra_assistant)]
    return msgs


@pytest.mark.parametrize(
    "users,expected",
    [
        (1, False),
        (4, False),
        (5, False),
        (6, True),
        (7, False),
        (10, False),
        (11, True),
        (16, True),
    ],
)
def test_needs_compaction_schedule(users, expected):
    assert _needs_compaction(_conv(users)) is expected


def test_needs_compaction_ignores_assistant_messages():
    assert _needs_compaction(_conv(users=3, extra_assistant=20)) is False


def test_turn_count_counts_only_user_messages():
    msgs = [_Msg("user"), _Msg("assistant"), _Msg("user"), _Msg("assistant"), _Msg("user")]
    assert _turn_count(msgs) == 3


async def test_search_returns_memory_strings(monkeypatch):
    monkeypatch.setattr(settings, "memory_enabled", True)
    monkeypatch.setattr(memory_manager, "_client", _FakeClient(results=["a", "b"]))
    found = await memory_manager.search("conv-1", "query")
    assert found == ["a", "b"]


async def test_search_disabled_returns_empty(monkeypatch):
    monkeypatch.setattr(settings, "memory_enabled", False)
    monkeypatch.setattr(memory_manager, "_client", _FakeClient(results=["a"]))
    assert await memory_manager.search("conv-1", "query") == []


async def test_search_failure_is_tolerant(monkeypatch):
    monkeypatch.setattr(settings, "memory_enabled", True)
    monkeypatch.setattr(memory_manager, "_client", _FakeClient(raise_on="search"))
    assert await memory_manager.search("conv-1", "query") == []


async def test_add_turns_calls_client(monkeypatch):
    monkeypatch.setattr(settings, "memory_enabled", True)
    fake = _FakeClient()
    monkeypatch.setattr(memory_manager, "_client", fake)
    await memory_manager.add_turns("conv-1", [{"role": "user", "content": "hi"}])
    assert fake.add_calls == [([{"role": "user", "content": "hi"}], "conv-1")]


async def test_add_turns_failure_is_tolerant(monkeypatch):
    monkeypatch.setattr(settings, "memory_enabled", True)
    monkeypatch.setattr(memory_manager, "_client", _FakeClient(raise_on="add"))
    assert await memory_manager.add_turns("conv-1", [{"role": "user", "content": "hi"}]) == {
        "results": []
    }


async def test_add_turns_skipped_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "memory_enabled", False)
    fake = _FakeClient()
    monkeypatch.setattr(memory_manager, "_client", fake)
    result = await memory_manager.add_turns("conv-1", [{"role": "user", "content": "hi"}])
    assert result == {"results": []}
    assert fake.add_calls == []


async def test_delete_conversation(monkeypatch):
    monkeypatch.setattr(settings, "memory_enabled", True)
    fake = _FakeClient()
    monkeypatch.setattr(memory_manager, "_client", fake)
    await memory_manager.delete_conversation("conv-1")
    assert fake.delete_calls == ["conv-1"]
