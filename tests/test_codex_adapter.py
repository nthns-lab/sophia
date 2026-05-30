import asyncio

from teamlead.adapters.codex.adapter import CodexBackend
from teamlead.ports.worker import WorkSpec


def test_missing_binary_returns_not_ok():
    backend = CodexBackend(codex_bin="definitely_not_a_real_codex_xyz")
    res = asyncio.run(backend.run(WorkSpec(instruction="hi")))
    assert res.ok is False
    assert "찾을 수 없음" in res.summary


def test_parse_prefers_final_message():
    backend = CodexBackend()
    res = backend._parse("최종 메시지", '{"message":"무시됨"}'.encode(), b"", returncode=0)
    assert res.ok and res.summary == "최종 메시지"


def test_parse_falls_back_to_jsonl():
    backend = CodexBackend()
    stdout = '{"message":"부분 "}\nnoise\n{"text":"응답"}\n'.encode()
    res = backend._parse("", stdout, b"", returncode=0)
    assert res.summary == "부분 응답"


def test_parse_falls_back_to_stderr():
    backend = CodexBackend()
    res = backend._parse("", b"", b"boom error", returncode=1)
    assert res.ok is False
    assert "boom error" in res.summary


def test_capabilities_isolation_follows_base_repo():
    assert CodexBackend().capabilities().worktree_isolation is False
    assert CodexBackend(base_repo="/some/repo").capabilities().worktree_isolation is True


def test_default_timeout_not_six_hours():
    assert CodexBackend().timeout_s <= 60 * 60


def test_implements_worker_port():
    # 같은 포트를 구현하는지 — core 가 claude/codex 를 구분 못 해야 한다
    from teamlead.ports.worker import WorkerBackend
    assert isinstance(CodexBackend(), WorkerBackend)
