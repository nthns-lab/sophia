import asyncio

from teamlead.adapters.fake_worker import FakeWorkerBackend
from teamlead.adapters.thinker.fake import FakeThinker
from teamlead.core.loop.scheduler import Scheduler
from teamlead.core.manager.director import Director
from teamlead.core.state.handoff import Handoff

from .conftest import noop_sleep, zero_clock


def _run(sched: Scheduler):
    reports: list[str] = []
    ho = asyncio.run(sched.run(report=reports.append))
    return ho, reports


def test_premise_flow_writes_handoff(tmp_path):
    thinker = FakeThinker(script=[
        {"premises": [
            {"id": "a", "statement": "A", "rationale": "r"},
            {"id": "b", "statement": "B", "rationale": "r"},
        ]},
        "두 전제로 진행해 모두 완료.",
    ])
    backend = FakeWorkerBackend()
    sched = Scheduler(
        backend=backend,
        director=Director(goal="목표"),
        thinker=thinker,
        goal="목표",
        handoff_path=str(tmp_path / "h.json"),
        max_cycles=1,
        clock=zero_clock,
        sleep=noop_sleep,
        pending_requests=["사용자 요청"],
    )
    ho, reports = _run(sched)
    assert len(backend.runs) == 2            # 전제 2개 병렬 실행
    assert len(ho.decisions) == 2            # 둘 다 성공 흡수
    assert reports == ["두 전제로 진행해 모두 완료."]
    assert (tmp_path / "h.json").exists()
    assert ho.status == "done"


def test_idle_replenish_generates_work(tmp_path):
    # pending 없음, director 큐 비어있음 → replenish 가 새 주제 생성 → 다음 사이클 실행
    thinker = FakeThinker(script=[
        {"topics": ["새 리서치 주제"]},   # replenish (사이클1)
        "리서치 완료 보고.",              # 단건 보고 (사이클2)
    ])
    backend = FakeWorkerBackend()
    sched = Scheduler(
        backend=backend,
        director=Director(goal="목표"),
        thinker=thinker,
        goal="목표",
        handoff_path=str(tmp_path / "h.json"),
        max_cycles=2,
        clock=zero_clock,
        sleep=noop_sleep,
    )
    ho, reports = _run(sched)
    assert len(backend.runs) == 1            # 자가 생성된 리서치 1건 실행
    assert "리서치 완료 보고." in reports


def test_insights_surfaced_first(tmp_path):
    sched = Scheduler(
        backend=FakeWorkerBackend(),
        director=Director(goal="목표", insights=["선제 인사이트"]),
        thinker=FakeThinker(script=[{"topics": []}]),
        goal="목표",
        handoff_path=str(tmp_path / "h.json"),
        max_cycles=1,
        clock=zero_clock,
        sleep=noop_sleep,
    )
    _, reports = _run(sched)
    assert reports[0] == "선제 인사이트"


def test_reports_persisted_to_handoff(tmp_path):
    # 6h 후 돌아온 사용자가 읽을 수 있도록 보고가 handoff 에 영속화되는지
    thinker = FakeThinker(script=[
        {"premises": [{"id": "a", "statement": "A", "rationale": "r"}]},
        "전제 A로 진행해 완료했습니다.",
    ])
    hp = tmp_path / "h.json"
    sched = Scheduler(
        backend=FakeWorkerBackend(),
        director=Director(goal="목표", insights=["선제 인사이트"]),
        thinker=thinker,
        goal="목표",
        handoff_path=str(hp),
        max_cycles=1,
        clock=zero_clock,
        sleep=noop_sleep,
        pending_requests=["요청"],
    )
    ho = asyncio.run(sched.run(report=lambda _m: None))
    texts = [r["text"] for r in ho.reports]
    assert "선제 인사이트" in texts
    assert "전제 A로 진행해 완료했습니다." in texts
    # 디스크에도 남아야(재시작·사후열람)
    reloaded = Handoff.load(hp)
    assert len(reloaded.reports) == len(ho.reports)
    assert all("at" in r and "text" in r for r in reloaded.reports)


def test_report_exception_does_not_kill_loop(tmp_path):
    def bad_report(_msg):
        raise RuntimeError("출력 장치 고장")

    sched = Scheduler(
        backend=FakeWorkerBackend(),
        director=Director(goal="목표", insights=["인사이트"]),
        thinker=FakeThinker(script=[
            {"premises": [{"id": "a", "statement": "A", "rationale": "r"}]},
            "보고",
        ]),
        goal="목표",
        handoff_path=str(tmp_path / "h.json"),
        max_cycles=1,
        clock=zero_clock,
        sleep=noop_sleep,
        pending_requests=["요청"],
    )
    # report 가 매번 던져도 run 은 정상 종료해야 한다
    ho = asyncio.run(sched.run(report=bad_report))
    assert isinstance(ho, Handoff)
    assert len(ho.decisions) == 1  # 작업 자체는 진행됨


def test_per_cycle_deadline_bounds_overrun(tmp_path):
    # 한 사이클의 일꾼이 남은 예산보다 오래 걸려도, 루프는 max_runtime_s 근처에서 끊겨야 한다.
    # (zero_clock 이 아닌 실제 시간 + 실제 sleep 로 검증)
    import time

    slow_backend = FakeWorkerBackend(latency=5.0)  # 5초 — 예산보다 훨씬 김
    sched = Scheduler(
        backend=slow_backend,
        director=Director(goal="목표"),
        thinker=FakeThinker(script=[
            {"premises": [{"id": "a", "statement": "A", "rationale": "r"}]},
            "보고",
        ]),
        goal="목표",
        handoff_path=str(tmp_path / "h.json"),
        max_runtime_s=0.2,        # 0.2초 예산
        pending_requests=["요청"],
        # clock/sleep 은 실제(time.monotonic / asyncio.sleep) 사용
    )
    t0 = time.monotonic()
    ho = asyncio.run(sched.run(report=lambda _m: None))
    elapsed = time.monotonic() - t0
    assert elapsed < 2.0          # 5초 일꾼에 끌려가지 않고 데드라인에 끊김
    assert isinstance(ho, Handoff)


def test_max_cycles_bounds_loop(tmp_path):
    # thinker 가 매번 빈 topics → 영원히 idle 이어도 max_cycles 가 끊는다
    sched = Scheduler(
        backend=FakeWorkerBackend(),
        director=Director(goal="목표"),
        thinker=FakeThinker(),  # script 없음 → schema 합성으로 {"topics":[...]}
        goal="목표",
        handoff_path=str(tmp_path / "h.json"),
        max_cycles=3,
        clock=zero_clock,
        sleep=noop_sleep,
    )
    ho, _ = _run(sched)
    assert isinstance(ho, Handoff)  # 무한루프 없이 반환
