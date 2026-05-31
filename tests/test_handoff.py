from sophia.core.manager.premise import Premise, PremiseOutcome
from sophia.core.state.handoff import Decision, Handoff
from sophia.ports.worker import WorkResult


def test_roundtrip(tmp_path):
    h = Handoff(session_id="s", goal="g", decisions=[Decision(id="D1", statement="x", why="w")])
    p = tmp_path / "h.json"
    h.save(p)
    loaded = Handoff.load(p)
    assert loaded.decisions[0].id == "D1"
    assert loaded.goal == "g"


def test_absorb_maps_ok_and_fail():
    h = Handoff(session_id="s")
    outcomes = [
        PremiseOutcome(Premise("a", "전제A"), WorkResult(summary="좋음", ok=True,
                       artifacts=[{"path": "x"}])),
        PremiseOutcome(Premise("b", "전제B"), WorkResult(summary="나쁨", ok=False)),
    ]
    h.absorb(outcomes)
    assert [d.id for d in h.decisions] == ["a"]          # 성공 → decision
    assert h.discarded[0]["what"] == "전제B"             # 실패 → discarded(재시도 방지)
    assert h.artifacts == [{"path": "x"}]


def test_add_report_records_and_caps():
    h = Handoff(session_id="s", max_items=3)
    for i in range(5):
        h.add_report(f"보고{i}", at=float(i))
    assert len(h.reports) == 3                 # 상한
    assert h.reports[-1] == {"at": 4.0, "text": "보고4"}  # 최신 유지


def test_reports_survive_roundtrip(tmp_path):
    h = Handoff(session_id="s")
    h.add_report("무엇을 전제로 했는지", at=12.5)
    p = tmp_path / "h.json"
    h.save(p)
    loaded = Handoff.load(p)
    assert loaded.reports == [{"at": 12.5, "text": "무엇을 전제로 했는지"}]


def test_absorb_caps_unbounded_growth():
    h = Handoff(session_id="s", max_items=10)
    for i in range(50):
        h.absorb([PremiseOutcome(Premise(f"p{i}", f"전제{i}"),
                                 WorkResult(summary="ok", ok=True))])
    assert len(h.decisions) == 10                        # 6h 무한증가 방지
    assert h.decisions[-1].id == "p49"                   # 최신 유지
