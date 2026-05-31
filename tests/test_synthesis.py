import asyncio

from sophia.adapters.fake_worker import FakeWorkerBackend
from sophia.adapters.thinker.fake import FakeThinker
from sophia.core.loop.scheduler import Scheduler
from sophia.core.manager.director import Director
from sophia.core.manager.premise import Premise, PremiseOutcome
from sophia.core.manager.synthesis import synthesize
from sophia.core.state.handoff import Handoff
from sophia.ports.worker import WorkResult

from .conftest import noop_sleep, zero_clock


def _ok(pid, summary="r"):
    return PremiseOutcome(Premise(pid, f"전제{pid}"), WorkResult(summary=summary, ok=True))


# ---------- synthesize() ----------

def test_synthesize_picks_winner():
    th = FakeThinker(script=[{
        "chosen_id": "b", "rationale": "B가 견고",
        "rejected": [{"id": "a", "why": "확장성 부족"}], "grafts": ["A의 단순함"],
    }])
    s = asyncio.run(synthesize("요청", [_ok("a"), _ok("b")], th))
    assert s.chosen_id == "b"
    assert s.rejected == [{"id": "a", "why": "확장성 부족"}]
    assert s.grafts == ["A의 단순함"]


def test_synthesize_none_when_single_success():
    assert asyncio.run(synthesize("q", [_ok("a")], FakeThinker())) is None


def test_synthesize_none_when_no_success():
    fail = PremiseOutcome(Premise("a", "A"), WorkResult(summary="실패", ok=False))
    assert asyncio.run(synthesize("q", [fail], FakeThinker())) is None


def test_synthesize_hallucinated_id_falls_back():
    th = FakeThinker(script=[{"chosen_id": "없는id", "rationale": "x", "rejected": []}])
    s = asyncio.run(synthesize("q", [_ok("a"), _ok("b")], th))
    assert s.chosen_id == "a"            # 폴백: 첫 성공안
    assert "폴백" in s.rationale


def test_synthesize_thinker_error_falls_back():
    class Boom(FakeThinker):
        async def think(self, *a, **k):
            raise RuntimeError("x")
    s = asyncio.run(synthesize("q", [_ok("a"), _ok("b")], Boom()))
    assert s.chosen_id == "a"
    assert len(s.rejected) == 1 and s.rejected[0]["id"] == "b"


# ---------- handoff.absorb_with_synthesis ----------

def test_absorb_with_synthesis_records_chosen_and_rejected():
    from sophia.core.manager.synthesis import Synthesis
    h = Handoff(session_id="s")
    outs = [_ok("a", "A결과"), _ok("b", "B결과")]
    syn = Synthesis(chosen_id="b", rationale="B 채택 이유",
                    rejected=[{"id": "a", "why": "기각 이유"}])
    h.absorb_with_synthesis("요청", outs, syn)
    assert [d.id for d in h.decisions] == ["b"]        # 채택만 decision
    assert h.decisions[0].why == "B 채택 이유"
    assert h.discarded[0]["what"] == "전제a"           # 나머지는 기각
    assert h.discarded[0]["why"] == "기각 이유"
    assert h.syntheses[0]["chosen"] == "b"


# ---------- scheduler integration ----------

def test_scheduler_synthesis_keeps_only_winner(tmp_path):
    thinker = FakeThinker(script=[
        {"premises": [                                  # derive: 2 전제
            {"id": "a", "statement": "A안", "rationale": "r"},
            {"id": "b", "statement": "B안", "rationale": "r"},
        ]},
        {"chosen_id": "a", "rationale": "A가 우월",       # synthesize
         "rejected": [{"id": "b", "why": "복잡함"}]},
        "보고",                                          # report
    ])
    backend = FakeWorkerBackend()
    sched = Scheduler(
        backend=backend, director=Director(goal="g"), thinker=thinker, goal="g",
        handoff_path=str(tmp_path / "h.json"), max_cycles=1,
        clock=zero_clock, sleep=noop_sleep, pending_requests=["요청"],
        synthesize=True,
    )
    ho = asyncio.run(sched.run(report=lambda _m: None))
    assert len(backend.runs) == 2                       # 둘 다 실행은 됨
    assert [d.id for d in ho.decisions] == ["a"]        # 결정은 승자만
    assert any(d["what"] == "B안" for d in ho.discarded)
    assert ho.syntheses[0]["chosen"] == "a"


def test_scheduler_no_synthesis_keeps_all(tmp_path):
    # synthesize=False(기본) → 기존 동작: 성공 전제 전부 decision
    thinker = FakeThinker(script=[
        {"premises": [
            {"id": "a", "statement": "A안", "rationale": "r"},
            {"id": "b", "statement": "B안", "rationale": "r"},
        ]},
        "보고",
    ])
    sched = Scheduler(
        backend=FakeWorkerBackend(), director=Director(goal="g"), thinker=thinker, goal="g",
        handoff_path=str(tmp_path / "h.json"), max_cycles=1,
        clock=zero_clock, sleep=noop_sleep, pending_requests=["요청"],
    )
    ho = asyncio.run(sched.run(report=lambda _m: None))
    assert sorted(d.id for d in ho.decisions) == ["a", "b"]   # 둘 다 남음
    assert ho.syntheses == []


def test_synthesis_survives_handoff_roundtrip(tmp_path):
    from sophia.core.manager.synthesis import Synthesis
    h = Handoff(session_id="s")
    h.absorb_with_synthesis("요청", [_ok("a"), _ok("b")],
                            Synthesis(chosen_id="a", rationale="이유",
                                      rejected=[{"id": "b", "why": "기각"}], grafts=["g1"]))
    p = tmp_path / "h.json"
    h.save(p)
    loaded = Handoff.load(p)
    assert loaded.syntheses[0]["chosen"] == "a"
    assert loaded.syntheses[0]["grafts"] == ["g1"]
