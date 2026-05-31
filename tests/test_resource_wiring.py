import asyncio

from sophia.adapters.fake_worker import FakeWorkerBackend
from sophia.adapters.resource.fake import FakeResourceGovernor
from sophia.adapters.thinker.fake import FakeThinker
from sophia.core.loop.scheduler import Scheduler
from sophia.core.manager.director import Director
from sophia.core.manager.premise import Premise, dispatch_parallel

from .conftest import noop_sleep, zero_clock


def test_dispatch_respects_max_concurrency():
    # 동시성 1로 묶으면 한 번에 하나씩만 실행 — 최대 동시 실행 수가 1이어야
    import asyncio as aio

    live = 0
    peak = 0

    class CountingBackend(FakeWorkerBackend):
        async def run(self, spec):
            nonlocal live, peak
            live += 1
            peak = max(peak, live)
            await aio.sleep(0.01)
            live -= 1
            return await super().run(spec)

    premises = [Premise(str(i), f"P{i}") for i in range(5)]
    outcomes = asyncio.run(
        dispatch_parallel(premises, CountingBackend(), max_concurrency=1)
    )
    assert len(outcomes) == 5
    assert peak == 1                       # 세마포어가 동시 실행을 1로 묶음


def test_governor_throttles_scheduler(tmp_path):
    # 거버너가 동시성 1을 강제해도 전제는 전부 실행되어야(직렬화될 뿐)
    thinker = FakeThinker(script=[
        {"premises": [
            {"id": "a", "statement": "A", "rationale": "r"},
            {"id": "b", "statement": "B", "rationale": "r"},
            {"id": "c", "statement": "C", "rationale": "r"},
        ]},
        "보고",
    ])
    backend = FakeWorkerBackend()
    sched = Scheduler(
        backend=backend, director=Director(goal="g"), thinker=thinker, goal="g",
        handoff_path=str(tmp_path / "h.json"), max_cycles=1,
        clock=zero_clock, sleep=noop_sleep, pending_requests=["요청"],
        governor=FakeResourceGovernor(force=1),
    )
    ho = asyncio.run(sched.run(report=lambda _m: None))
    assert len(backend.runs) == 3          # 동시성 1이어도 3개 다 실행
    assert len(ho.decisions) == 3


def test_no_governor_means_full_parallel(tmp_path):
    thinker = FakeThinker(script=[
        {"premises": [{"id": "a", "statement": "A", "rationale": "r"}]}, "보고",
    ])
    backend = FakeWorkerBackend()
    sched = Scheduler(
        backend=backend, director=Director(goal="g"), thinker=thinker, goal="g",
        handoff_path=str(tmp_path / "h.json"), max_cycles=1,
        clock=zero_clock, sleep=noop_sleep, pending_requests=["요청"],
        # governor 없음
    )
    ho = asyncio.run(sched.run(report=lambda _m: None))
    assert len(ho.decisions) == 1
