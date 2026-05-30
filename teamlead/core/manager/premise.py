"""전제(premise) 엔진 — 해법공간이 아니라 '전제공간'을 병렬 탐색.

한 요청을 여러 전제(해석/프레이밍)로 갈라 독립 일꾼에 동시에 굴린다.
worktree 격리로 병렬 일꾼이 서로의 파일을 안 건드린다.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from ...ports.thinker import Thinker
from ...ports.worker import WorkerBackend, WorkResult, WorkSpec
from ...prompts import templates


@dataclass
class Premise:
    id: str
    statement: str
    rationale: str = ""


@dataclass
class PremiseOutcome:
    premise: Premise
    result: WorkResult


async def derive_premises(request: str, thinker: Thinker, n: int = 3) -> list[Premise]:
    """요청에서 서로 다른 전제 N개를 도출. 실패 시 단일 전제로 안전 폴백."""
    try:
        out = await thinker.think(
            templates.PREMISE_DERIVE.format(request=request, n=n),
            system=templates.SYSTEM_MANAGER,
            schema=templates.PREMISE_SCHEMA,
        )
        premises = [
            Premise(id=p["id"], statement=p["statement"], rationale=p.get("rationale", ""))
            for p in out.get("premises", [])
        ]
    except Exception:
        premises = []
    if not premises:
        premises = [Premise(id="default", statement=request, rationale="단일 전제 폴백")]
    return premises[:n]


async def dispatch_parallel(
    premises: list[Premise], backend: WorkerBackend, context: str = ""
) -> list[PremiseOutcome]:
    """전제마다 독립 일꾼으로 병렬 실행. 한 전제가 터져도 나머지는 진행."""
    specs = [
        WorkSpec(
            instruction=templates.WORKER_PREMISE.format(premise=p.statement),
            context=context,
            premise_id=p.id,
            isolation=True,
        )
        for p in premises
    ]
    results = await asyncio.gather(
        *(backend.run(s) for s in specs), return_exceptions=True
    )
    outcomes: list[PremiseOutcome] = []
    for p, r in zip(premises, results):
        if isinstance(r, Exception):
            r = WorkResult(summary=f"예외: {r}", ok=False)
        outcomes.append(PremiseOutcome(premise=p, result=r))
    return outcomes
