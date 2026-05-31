"""반응 시뮬레이션 — 보고 후 회신을 기다리는 대신 "사용자가 어떻게 반응할까"를
예측해 선제 작업을 만든다.

사람은 두 번 일하기를 극도로 싫어한다. 그래서 회신을 받고서야 다음 일을 한다.
에이전트는 그럴 이유가 없다 — 보고를 올린 뒤 가능한 반응을 미리 굴려보고, 그중
해볼 만한 일을 먼저 해둔다. 비효율처럼 보여도 멈추지 않는다는 게 핵심이다.

무한 폭주 방지: 예측은 '실제 요청의 보고'에서만 1단계(depth-1) 파생된다.
예측으로 생긴 선제 작업은 또 예측을 낳지 않는다(scheduler 가 큐를 분리해 강제).
"""
from __future__ import annotations

from ...ports.thinker import Thinker
from ...prompts import templates


async def anticipate(report: str, goal: str, thinker: Thinker, width: int = 2) -> list[str]:
    """보고에 대한 예상 반응 → 선제 작업 지시문 리스트. 실패 시 빈 리스트(폴백)."""
    if width <= 0 or not report.strip():
        return []
    try:
        out = await thinker.think(
            templates.ANTICIPATE.format(report=report, goal=goal or "(목표 미설정)", n=width),
            system=templates.SYSTEM_MANAGER,
            schema=templates.ANTICIPATE_SCHEMA,
        )
        tasks = [
            a["preemptive_task"]
            for a in out.get("anticipations", [])
            if a.get("preemptive_task", "").strip()
        ]
    except Exception:
        tasks = []
    return tasks[:width]
