import asyncio

from sophia.adapters.thinker.fake import FakeThinker
from sophia.core.manager.director import MAX_RESEARCH_QUEUE, Director


def test_monitor_targets_rotate_round_robin():
    d = Director(monitor_targets=["X", "Y"], monitor_cooldown=1)
    got = []
    for _ in range(4):
        spec = d.next_task()
        assert spec is not None
        got.append(spec.instruction)
    # X, Y 가 번갈아 나와야 함 ([0]만 무한반복하면 안 됨)
    assert "X" in got[0] and "Y" in got[1]
    assert "X" in got[2] and "Y" in got[3]


def test_monitor_cooldown_yields_idle_cycles():
    d = Director(monitor_targets=["X"], monitor_cooldown=3)
    results = [d.next_task() for _ in range(3)]
    # cooldown=3 → 처음 2번은 None(쉼), 3번째에 발행
    assert results[0] is None and results[1] is None
    assert results[2] is not None


def test_has_work_false_when_only_monitoring():
    # 모니터링만 있으면 '항상 일감'이 아니어야 루프가 쉴 수 있다
    d = Director(monitor_targets=["X"])
    assert d.has_work() is False


def test_replenish_dedups_seen_topics():
    thinker = FakeThinker(script=[{"topics": ["t1", "t2"]}, {"topics": ["t2", "t3"]}])
    d = Director(goal="g")
    n1 = asyncio.run(d.replenish(thinker))
    n2 = asyncio.run(d.replenish(thinker))
    assert n1 == 2          # t1, t2
    assert n2 == 1          # t3 만 (t2 중복 제거)
    assert d.research_topics == ["t1", "t2", "t3"]


def test_replenish_respects_queue_cap():
    d = Director(goal="g", research_topics=["x"] * MAX_RESEARCH_QUEUE)
    n = asyncio.run(d.replenish(FakeThinker(script=[{"topics": ["new"]}])))
    assert n == 0           # 큐가 꽉 차면 더 안 받음
