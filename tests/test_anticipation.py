import asyncio

from sophia.adapters.fake_worker import FakeWorkerBackend
from sophia.adapters.thinker.fake import FakeThinker
from sophia.core.loop.scheduler import Scheduler
from sophia.core.manager.anticipation import anticipate
from sophia.core.manager.director import Director
from sophia.core.state.handoff import Handoff

from .conftest import noop_sleep, zero_clock


def test_anticipate_parses_tasks():
    thinker = FakeThinker(script=[{"anticipations": [
        {"reaction": "더 자세히 보자", "preemptive_task": "상세 분석 준비"},
        {"reaction": "다른 안은?", "preemptive_task": "대안 B 초안"},
    ]}])
    tasks = asyncio.run(anticipate("보고 본문", "목표", thinker, width=2))
    assert tasks == ["상세 분석 준비", "대안 B 초안"]


def test_anticipate_empty_report_returns_nothing():
    assert asyncio.run(anticipate("", "목표", FakeThinker(), width=2)) == []


def test_anticipate_failure_returns_empty():
    class Boom(FakeThinker):
        async def think(self, *a, **k):
            raise RuntimeError("x")
    assert asyncio.run(anticipate("보고", "목표", Boom(), width=2)) == []


def test_scheduler_generates_speculative_after_real_report(tmp_path):
    thinker = FakeThinker(script=[
        {"premises": [{"id": "a", "statement": "A", "rationale": "r"}]},
        "실제 보고",
        {"anticipations": [
            {"reaction": "r1", "preemptive_task": "선제작업1"},
            {"reaction": "r2", "preemptive_task": "선제작업2"},
        ]},
        {"premises": [{"id": "s1", "statement": "S1", "rationale": "r"}]},
        "선제 보고1",
        {"premises": [{"id": "s2", "statement": "S2", "rationale": "r"}]},
        "선제 보고2",
    ])
    backend = FakeWorkerBackend()
    sched = Scheduler(
        backend=backend, director=Director(goal="g"), thinker=thinker, goal="g",
        handoff_path=str(tmp_path / "h.json"), max_cycles=3,
        clock=zero_clock, sleep=noop_sleep, pending_requests=["실제요청"],
        anticipate=True, anticipation_width=2,
    )
    ho = asyncio.run(sched.run(report=lambda _m: None))
    ids = [d.id for d in ho.decisions]
    assert "a" in ids and "s1" in ids and "s2" in ids
    assert sched.speculative_requests == []
    assert ho.status == "done"


def test_speculative_does_not_anticipate_again(tmp_path):
    thinker = FakeThinker(script=[
        {"premises": [{"id": "a", "statement": "A", "rationale": "r"}]},
        "실제 보고",
        {"anticipations": [{"reaction": "r1", "preemptive_task": "선제작업1"}]},
        {"premises": [{"id": "s1", "statement": "S1", "rationale": "r"}]},
        "선제 보고1",
    ])
    sched = Scheduler(
        backend=FakeWorkerBackend(), director=Director(goal="g"), thinker=thinker, goal="g",
        handoff_path=str(tmp_path / "h.json"), max_cycles=2,
        clock=zero_clock, sleep=noop_sleep, pending_requests=["실제요청"],
        anticipate=True, anticipation_width=1,
    )
    asyncio.run(sched.run(report=lambda _m: None))
    assert sched.speculative_requests == []


def test_max_speculative_caps_queue(tmp_path):
    thinker = FakeThinker(script=[
        {"premises": [{"id": "a", "statement": "A", "rationale": "r"}]},
        "실제 보고",
        {"anticipations": [
            {"reaction": "r1", "preemptive_task": "t1"},
            {"reaction": "r2", "preemptive_task": "t2"},
            {"reaction": "r3", "preemptive_task": "t3"},
        ]},
    ])
    sched = Scheduler(
        backend=FakeWorkerBackend(), director=Director(goal="g"), thinker=thinker, goal="g",
        handoff_path=str(tmp_path / "h.json"), max_cycles=1,
        clock=zero_clock, sleep=noop_sleep, pending_requests=["실제요청"],
        anticipate=True, anticipation_width=3, max_speculative=2,
    )
    asyncio.run(sched.run(report=lambda _m: None))
    assert len(sched.speculative_requests) == 2


def test_anticipate_off_by_default(tmp_path):
    thinker = FakeThinker(script=[
        {"premises": [{"id": "a", "statement": "A", "rationale": "r"}]}, "보고",
    ])
    sched = Scheduler(
        backend=FakeWorkerBackend(), director=Director(goal="g"), thinker=thinker, goal="g",
        handoff_path=str(tmp_path / "h.json"), max_cycles=1,
        clock=zero_clock, sleep=noop_sleep, pending_requests=["요청"],
    )
    asyncio.run(sched.run(report=lambda _m: None))
    assert sched.speculative_requests == []


def test_speculative_queue_persisted_and_resumed(tmp_path):
    hp = str(tmp_path / "h.json")
    thinker1 = FakeThinker(script=[
        {"premises": [{"id": "a", "statement": "A", "rationale": "r"}]},
        "실제 보고",
        {"anticipations": [
            {"reaction": "r1", "preemptive_task": "선제1"},
            {"reaction": "r2", "preemptive_task": "선제2"},
        ]},
    ])
    s1 = Scheduler(
        backend=FakeWorkerBackend(), director=Director(goal="g"), thinker=thinker1, goal="g",
        handoff_path=hp, max_cycles=1, clock=zero_clock, sleep=noop_sleep,
        pending_requests=["실제요청"], anticipate=True, anticipation_width=2,
    )
    asyncio.run(s1.run(report=lambda _m: None))
    saved = Handoff.load(hp)
    assert saved.speculative_requests == ["선제1", "선제2"]

    thinker2 = FakeThinker(script=[
        {"premises": [{"id": "s1", "statement": "S1", "rationale": "r"}]}, "선제 보고1",
    ])
    s2 = Scheduler(
        backend=FakeWorkerBackend(), director=Director(goal="g"), thinker=thinker2, goal="g",
        handoff_path=hp, max_cycles=1, clock=zero_clock, sleep=noop_sleep,
        resume=True, anticipate=True, anticipation_width=2,
    )
    assert s2.speculative_requests == []
    asyncio.run(s2.run(report=lambda _m: None))
    assert s2.speculative_requests == ["선제2"]
