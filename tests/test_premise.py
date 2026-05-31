import asyncio

from sophia.adapters.fake_worker import FakeWorkerBackend
from sophia.adapters.thinker.fake import FakeThinker
from sophia.core.manager.premise import derive_premises, dispatch_parallel


def test_derive_premises_parses_thinker_output():
    thinker = FakeThinker(
        script=[{"premises": [
            {"id": "a", "statement": "전제A", "rationale": "r"},
            {"id": "b", "statement": "전제B", "rationale": "r"},
        ]}]
    )
    premises = asyncio.run(derive_premises("요청", thinker, n=3))
    assert [p.id for p in premises] == ["a", "b"]


def test_derive_premises_falls_back_to_single():
    class Boom(FakeThinker):
        async def think(self, *a, **k):
            raise RuntimeError("down")

    premises = asyncio.run(derive_premises("요청", Boom(), n=3))
    assert len(premises) == 1 and premises[0].id == "default"


def test_dispatch_parallel_runs_all_and_isolates_failure():
    from sophia.core.manager.premise import Premise

    backend = FakeWorkerBackend(fail_on={"b"})
    premises = [Premise("a", "A"), Premise("b", "B"), Premise("c", "C")]
    outcomes = asyncio.run(dispatch_parallel(premises, backend))
    assert len(outcomes) == 3
    oks = {o.premise.id: o.result.ok for o in outcomes}
    assert oks == {"a": True, "b": False, "c": True}
    # 모든 일꾼이 worktree 격리로 디스패치됐는지
    assert all(s.isolation for s in backend.runs)
