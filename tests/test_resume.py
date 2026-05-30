import asyncio

from teamlead.adapters.fake_worker import FakeWorkerBackend
from teamlead.adapters.thinker.fake import FakeThinker
from teamlead.core.loop.scheduler import Scheduler
from teamlead.core.manager.director import Director
from teamlead.core.state.handoff import Handoff

from .conftest import noop_sleep, zero_clock


def _sched(tmp_path, *, resume, pending, script):
    return Scheduler(
        backend=FakeWorkerBackend(),
        director=Director(goal="목표"),
        thinker=FakeThinker(script=script),
        goal="목표",
        handoff_path=str(tmp_path / "h.json"),
        max_cycles=1,
        clock=zero_clock,
        sleep=noop_sleep,
        resume=resume,
        pending_requests=pending,
    )


def test_resume_carries_forward_prior_record(tmp_path):
    # 1차 실행: 요청 1건 처리 → decisions 생김
    s1 = _sched(tmp_path, resume=False, pending=["요청A"], script=[
        {"premises": [{"id": "a", "statement": "A", "rationale": "r"}]}, "보고A",
    ])
    ho1 = asyncio.run(s1.run(report=lambda _m: None))
    assert len(ho1.decisions) == 1

    # 2차 실행(resume): 새 요청 처리하되 이전 기록을 이어받아야 함
    s2 = _sched(tmp_path, resume=True, pending=["요청B"], script=[
        {"premises": [{"id": "b", "statement": "B", "rationale": "r"}]}, "보고B",
    ])
    ho2 = asyncio.run(s2.run(report=lambda _m: None))
    ids = [d.id for d in ho2.decisions]
    assert "a" in ids and "b" in ids          # 이전(a) + 신규(b) 누적
    assert len(ho2.reports) >= 2              # 이전 보고도 이어받음


def test_resume_restores_pending_queue(tmp_path):
    # 1차: 요청 2건 중 1건만 처리(max_cycles=1) → 1건이 pending 으로 남아 저장됨
    s1 = Scheduler(
        backend=FakeWorkerBackend(),
        director=Director(goal="목표"),
        thinker=FakeThinker(script=[
            {"premises": [{"id": "a", "statement": "A", "rationale": "r"}]}, "보고",
        ]),
        goal="목표",
        handoff_path=str(tmp_path / "h.json"),
        max_cycles=1,
        clock=zero_clock,
        sleep=noop_sleep,
        pending_requests=["요청1", "요청2"],
    )
    ho1 = asyncio.run(s1.run(report=lambda _m: None))
    assert ho1.pending_requests == ["요청2"]   # 미완료 큐 저장됨
    assert ho1.status == "in_progress"

    # 2차(resume, caller 큐 비움): 저장된 요청2를 복원해 처리
    s2 = Scheduler(
        backend=FakeWorkerBackend(),
        director=Director(goal="목표"),
        thinker=FakeThinker(script=[
            {"premises": [{"id": "b", "statement": "B", "rationale": "r"}]}, "보고2",
        ]),
        goal="목표",
        handoff_path=str(tmp_path / "h.json"),
        max_cycles=1,
        clock=zero_clock,
        sleep=noop_sleep,
        resume=True,
        pending_requests=[],
    )
    assert s2.pending_requests == []
    ho2 = asyncio.run(s2.run(report=lambda _m: None))
    # 복원된 요청2가 처리되어 큐가 비고 done
    assert ho2.pending_requests == []
    assert ho2.status == "done"


def test_resume_ignores_different_goal(tmp_path):
    Handoff(session_id="s", goal="다른목표",
            pending_requests=["남은것"]).save(tmp_path / "h.json")
    s = _sched(tmp_path, resume=True, pending=["새요청"], script=[
        {"premises": [{"id": "x", "statement": "X", "rationale": "r"}]}, "보고",
    ])
    ho = asyncio.run(s.run(report=lambda _m: None))
    # goal 이 다르므로 이전 큐("남은것")를 복원하지 않고 새로 시작
    assert all(d.id != "남은것" for d in ho.decisions)
    assert "X" in [d.statement for d in ho.decisions]


def test_no_resume_starts_fresh(tmp_path):
    Handoff(session_id="s", goal="목표",
            pending_requests=["옛날요청"]).save(tmp_path / "h.json")
    s = _sched(tmp_path, resume=False, pending=["새요청"], script=[
        {"premises": [{"id": "n", "statement": "N", "rationale": "r"}]}, "보고",
    ])
    ho = asyncio.run(s.run(report=lambda _m: None))
    # resume=False → 이전 파일 무시, 새 기록만
    assert [d.id for d in ho.decisions] == ["n"]


def test_corrupt_handoff_does_not_crash_resume(tmp_path):
    (tmp_path / "h.json").write_text("{ broken json", encoding="utf-8")
    s = _sched(tmp_path, resume=True, pending=["요청"], script=[
        {"premises": [{"id": "a", "statement": "A", "rationale": "r"}]}, "보고",
    ])
    ho = asyncio.run(s.run(report=lambda _m: None))  # 손상돼도 죽지 않고 새로 시작
    assert ho.status == "done"
