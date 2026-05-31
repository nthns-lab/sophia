import asyncio

from sophia.adapters.thinker.fake import FakeThinker
from sophia.core.manager.premise import Premise, PremiseOutcome
from sophia.core.manager.reporter import _cap_sentences, to_premise_report
from sophia.ports.worker import WorkResult


def test_cap_sentences_enforces_under_five():
    long = "하나다. 둘이다. 셋이다. 넷이다. 다섯이다. 여섯이다."
    out = _cap_sentences(long, 5)
    # 5문장 '미만' → 최대 4문장
    assert out.count(".") <= 4


def test_cap_sentences_strips_report_formatting():
    out = _cap_sentences("줄1\n\n  줄2", 5)
    assert "\n" not in out


def test_cap_sentences_korean_no_space_after_period():
    # 한국어: 마침표 뒤 공백이 없어도 문장 분리·캡이 동작해야 함
    kr = "했습니다.다음으로했습니다.그리고했습니다.또했습니다.마지막했습니다.초과했습니다."
    out = _cap_sentences(kr, 5)
    assert out.count(".") <= 4  # 5문장 미만 강제


def test_cap_sentences_runaway_no_punctuation_char_budget():
    # 종결부호가 전혀 없는 한 덩어리도 글자수로 강제 컷
    out = _cap_sentences("가" * 2000, 5, char_budget=100)
    assert len(out) <= 100


def test_surface_insight_also_capped():
    from sophia.core.manager.reporter import surface_insight
    long = "하나다. 둘이다. 셋이다. 넷이다. 다섯이다. 여섯이다."
    out = surface_insight(long)
    assert out.count(".") <= 4  # 인사이트도 5문장 게이트 통과


def test_to_premise_report_uses_thinker():
    thinker = FakeThinker(script=["짧은 보고 한 줄."])
    outcomes = [PremiseOutcome(Premise("a", "A"), WorkResult(summary="ok", ok=True))]
    out = asyncio.run(to_premise_report(outcomes, thinker))
    assert out == "짧은 보고 한 줄."


def test_to_premise_report_falls_back_on_thinker_error():
    class Boom(FakeThinker):
        async def think(self, *a, **k):
            raise RuntimeError("x")

    outcomes = [PremiseOutcome(Premise("a", "A"), WorkResult(summary="결과", ok=True))]
    out = asyncio.run(to_premise_report(outcomes, Boom()))
    assert "전제[a]" in out  # 폴백은 원시 라인을 캡해 반환
