"""Synthesis — 여러 전제 갈래를 비교해 '하나를 채택, 나머지는 이유와 함께 기각'.

관리자의 핵심 행위다. 지금까지는 갈라서 병렬 실행만 하고 결과를 다 안고 갔다(절반의
관리자). synthesis 가 그 나머지 절반 — 결정 — 을 채운다.

성공한 전제 결과가 2개 이상일 때만 의미가 있다. 0~1개면 고를 게 없으니 그대로 통과.
실패 시(thinker 오류·이상한 id) 안전 폴백: 첫 성공 전제를 채택.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ...ports.thinker import Thinker
from ...prompts import templates
from .premise import PremiseOutcome


@dataclass
class Synthesis:
    chosen_id: str
    rationale: str
    rejected: list[dict] = field(default_factory=list)   # [{id, why}]
    grafts: list[str] = field(default_factory=list)


async def synthesize(
    request: str, outcomes: list[PremiseOutcome], thinker: Thinker
) -> Synthesis | None:
    """성공한 전제들을 비교해 승자 선택. 고를 게 없으면 None.

    None 반환 = synthesis 불필요(성공 0~1개). 이 경우 호출자는 기존 흐름 유지.
    """
    ok = [o for o in outcomes if o.result.ok]
    if len(ok) < 2:
        return None  # 비교할 게 없음

    valid_ids = {o.premise.id for o in ok}
    block = "\n".join(
        f"- 전제[{o.premise.id}] {o.premise.statement}\n  결과: {o.result.summary}"
        for o in ok
    )
    try:
        out = await thinker.think(
            templates.SYNTHESIZE.format(request=request, results=block),
            system=templates.SYSTEM_MANAGER,
            schema=templates.SYNTHESIZE_SCHEMA,
        )
        chosen = out.get("chosen_id", "")
        if chosen not in valid_ids:   # 환각 id 방어 → 폴백
            raise ValueError("chosen_id 가 유효하지 않음")
        # 기각 목록도 유효 id 만, 그리고 채택안은 제외
        rejected = [
            r for r in out.get("rejected", [])
            if r.get("id") in valid_ids and r.get("id") != chosen
        ]
        return Synthesis(
            chosen_id=chosen,
            rationale=out.get("rationale", ""),
            rejected=rejected,
            grafts=[g for g in out.get("grafts", []) if isinstance(g, str) and g.strip()],
        )
    except Exception:
        # 안전 폴백: 첫 성공 전제 채택, 나머지는 "비교 실패로 보류"
        first = ok[0].premise.id
        return Synthesis(
            chosen_id=first,
            rationale="(synthesis 폴백: 비교 실패, 첫 성공안 채택)",
            rejected=[{"id": o.premise.id, "why": "비교 실패로 보류"}
                      for o in ok if o.premise.id != first],
        )
