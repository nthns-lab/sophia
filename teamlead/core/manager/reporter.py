"""Reporter — 사용자 대면 출력 게이트.

규칙: 5문장 미만, 레포트 형태 금지, 전제 기반 사후 보고. 인지부하 최소화.
작업 모드 verbose 는 여기 통과하지 않고 내부 로그로만 남는다.
"""
from __future__ import annotations

import re

from ...ports.thinker import Thinker
from ...prompts import templates
from .premise import PremiseOutcome

MAX_SENTENCES = 5


def _cap_sentences(text: str, max_sentences: int, char_budget: int = 600) -> str:
    text = " ".join(text.split())  # 줄바꿈/중복공백 제거 → 비레포트화
    # 종결부호 뒤 공백 유무와 무관하게 문장을 잡는다(한국어는 마침표 뒤 공백이 없을 때가 많음).
    parts = [s.strip() for s in re.findall(r"[^.!?。…]*[.!?。…]+", text) if s.strip()]
    tail = re.sub(r"[^.!?。…]*[.!?。…]+", "", text).strip()  # 종결부호 없는 꼬리
    if tail:
        parts.append(tail)
    if not parts:  # 종결부호가 전혀 없는 한 덩어리 → 글자수로 강제 컷
        return text[:char_budget]
    capped = parts[: max_sentences - 1] if len(parts) >= max_sentences else parts
    return " ".join(capped)[:char_budget]  # 문장수 + 글자수 이중 게이트


async def to_premise_report(
    outcomes: list[PremiseOutcome], thinker: Thinker, max_sentences: int = MAX_SENTENCES
) -> str:
    """전제별 결과 → 5문장 미만 보고. thinker 실패 시 결정론적 폴백."""
    lines = []
    for o in outcomes:
        status = "완료" if o.result.ok else "실패"
        lines.append(f"- 전제[{o.premise.id}] {o.premise.statement}: {status} — {o.result.summary}")
    raw = "\n".join(lines)
    try:
        text = await thinker.think(
            templates.REPORT_COMPRESS.format(results=raw, n=max_sentences),
            system=templates.SYSTEM_MANAGER,
        )
    except Exception:
        text = raw
    return _cap_sentences(text, max_sentences)


def surface_insight(insight: str, max_sentences: int = MAX_SENTENCES) -> str:
    """무지시 상태에서 발견한 인사이트를 사용자에게 표면화. 5문장 게이트 동일 적용."""
    return _cap_sentences(insight, max_sentences)
