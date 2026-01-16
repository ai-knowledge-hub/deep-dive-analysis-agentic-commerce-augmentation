from __future__ import annotations

from shared.db.connection import init_db, set_database_path
from modules.memory.semantic import SemanticMemory
from modules.mcp.tools import image_analyze, memory_write, web_fetch


def test_web_fetch_requires_allowlist(monkeypatch):
    monkeypatch.delenv("WEB_FETCH_ALLOWLIST", raising=False)
    result = web_fetch.run("https://example.com")
    assert "error" in result
    assert "allowlist" in result["error"].lower()


def test_web_fetch_allowlist_allows(monkeypatch):
    monkeypatch.setenv("WEB_FETCH_ALLOWLIST", "example.com")

    class DummyResponse:
        def __init__(self):
            self.headers = {"Content-Type": "text/plain"}

        def read(self, _):
            return b"ok"

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        "modules.mcp.tools.web_fetch.urllib.request.urlopen",
        lambda *_, **__: DummyResponse(),
    )
    result = web_fetch.run("https://example.com/test")
    assert result["text"] == "ok"


def test_image_analyze_stub():
    result = image_analyze.run(image_url="https://example.com/image.png")
    assert result["status"] == "unavailable"


def test_memory_write_append_and_set(tmp_path, monkeypatch):
    db_path = tmp_path / "memory.db"
    set_database_path(db_path)
    init_db()

    memory_write.run(key="goals", value="Reduce back pain", mode="append")
    memory = SemanticMemory()
    assert "Reduce back pain" in memory.get("goals")

    memory_write.run(key="goals", values=["Improve focus"], mode="set")
    assert memory.get("goals") == ["Improve focus"]
