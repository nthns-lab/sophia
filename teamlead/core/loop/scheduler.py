"""Scheduler — 6시간 무인 롱런 루프 (중간관리자의 하루).

매 사이클:
 1) 인사이트 먼저 사용자에게 표면화
 2) 사용자 요청(pending_requests) 있으면 → 전제 병렬 탐색
 3) 없으면 director 자가 과업(리서치/모니터링) 단건 실행
 4) 그마저 없으면 director.replenish() 로 새 과업 생성 (절대 idle 로 안 죽음)
 5) 모든 결과는 5문장 보고 + 핸드오프에 흡수, 매 사이클 저장

종료 경계:
 - max_runtime_s: 벽시계 시간(실서비스, 기본 6h)
 - max_cycles:    사이클 수 상한(테스트/안전). None 이면 무제한
clock/sleep 을 주입받아 테스트에서 시간을 통제한다.
모든 일꾼/thinker 호출은 예외를 삼켜 6시간 동안 죽지 않는다.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from ...ports.retriever import Retriever
from ...ports.thinker import Thinker
from ...ports.worker import WorkerBackend, WorkResult, WorkSpec
from ..manager.director import Director
from ..manager.premise import (
    Premise,
    PremiseOutcome,
    derive_premises,
    dispatch_parallel,
)
from ..manager.reporter import surface_insight, to_premise_report
from ..state.handoff import Handoff


@dataclass
class Scheduler:
    backend: WorkerBackend
    director: Director
    thinker: Thinker
    retriever: Retriever | None = None
    session_id: str = "session"
    goal: str = ""
    handoff_path: str = "handoff.json"
    max_runtime_s: float = 6 * 3600
    max_cycles: int | None = None
    idle_sleep_s: float = 30.0
    premise_count: int = 3
    pending_requests: list[str] = field(default_factory=list)
    resume: bool = False  # True 면 기존 handoff_path 를 읽어 이어간다
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep

    async def run(self, report: Callable[[str], None] = print) -> Handoff:
        start = self.clock()
        ho = self._init_handoff()
        # 모든 보고를 handoff 에 영속화 + 사용자 콜백 호출(예외는 삼킴).
        # 이래야 6h 후 돌아온 사용자가 stdout 이 아니라 handoff.json 에서 읽을 수 있다.
        report = self._persisting_report(report, ho, start)
        cycles = 0
        while True:
            remaining = self.max_runtime_s - (self.clock() - start)
            if remaining <= 0:
                break
            if self.max_cycles is not None and cycles >= self.max_cycles:
                break
            cycles += 1

            for ins in self.director.drain_insights():
                report(surface_insight(ins))

            try:
                # 한 사이클의 작업이 남은 예산을 넘기지 못하게 강제(데드라인 상한).
                # 어댑터 30분 타임아웃과 별개로, 루프가 max_runtime_s 를 지키게 한다.
                await asyncio.wait_for(self._cycle(ho, report), timeout=remaining)
            except (asyncio.TimeoutError, TimeoutError):
                break  # 데드라인 초과 → 진행 중 작업을 끊고 종료

            ho.pending_requests = list(self.pending_requests)  # 재시작 대비 큐 영속
            self._safe_save(ho)

        ho.pending_requests = list(self.pending_requests)
        ho.status = "done" if not self.pending_requests else "in_progress"
        ho.next_action = self.pending_requests[0] if self.pending_requests else ""
        self._safe_save(ho)
        return ho

    def _init_handoff(self) -> Handoff:
        """resume=True 이고 같은 goal 의 이전 handoff 가 있으면 기록을 이어받는다.

        이어받는 것: decisions/discarded/artifacts/reports/glossary 등 누적 기록과
        미완료 pending_requests(caller 가 명시 큐를 안 줬을 때). goal 이 다르거나
        파일이 없으면 빈 핸드오프로 새로 시작한다.
        """
        fresh = Handoff(session_id=self.session_id, goal=self.goal)
        if not self.resume:
            return fresh
        prev = self._load_prev()
        if prev is None or prev.goal != self.goal:
            return fresh  # 다른 목표/없음 → 깨끗이 시작(잘못된 이어가기 방지)
        fresh.decisions = prev.decisions
        fresh.discarded = prev.discarded
        fresh.artifacts = prev.artifacts
        fresh.reports = prev.reports
        fresh.glossary = prev.glossary
        fresh.constraints = prev.constraints
        fresh.open_questions = prev.open_questions
        # caller 가 큐를 명시하지 않았으면 이전 미완료 큐를 복원
        if not self.pending_requests and prev.pending_requests:
            self.pending_requests = list(prev.pending_requests)
        return fresh

    def _load_prev(self) -> Handoff | None:
        from pathlib import Path

        try:
            if Path(self.handoff_path).exists():
                return Handoff.load(self.handoff_path)
        except Exception:
            return None  # 손상된 핸드오프로 6h 루프를 죽이지 않는다
        return None

    async def _cycle(self, ho: Handoff, report) -> None:
        """한 사이클의 본 작업. run() 이 데드라인(wait_for)으로 감싼다."""
        if self.pending_requests:
            await self._explore(self.pending_requests.pop(0), ho, report)
        elif (spec := self.director.next_task()) is not None:
            await self._single(spec, ho, report)
        else:
            added = await self.director.replenish(self.thinker)
            if not added and not self.director.has_work():
                await self.sleep(self.idle_sleep_s)

    def _persisting_report(
        self, report: Callable[[str], None], ho: Handoff, start: float
    ) -> Callable[[str], None]:
        def wrapped(msg: str) -> None:
            try:
                ho.add_report(msg, at=self.clock() - start)  # 영속화(상대 경과초)
            except Exception:
                pass
            try:
                report(msg)  # 사용자 콜백(stdout 등)
            except Exception:
                pass  # 보고 출력 실패로 루프를 멈추지 않는다
        return wrapped

    def _safe_save(self, ho: Handoff) -> None:
        try:
            ho.save(self.handoff_path)
        except OSError:
            pass  # 디스크 문제로 6h 루프를 죽이지 않는다

    async def _explore(self, request: str, ho: Handoff, report) -> None:
        """사용자 요청 → 전제 병렬 탐색."""
        context = ""
        if self.retriever is not None:
            try:
                hits = self.retriever.query(request, k=3)
                context = "\n".join(h["text"] for h in hits)
            except Exception:
                context = ""

        premises = await derive_premises(request, self.thinker, self.premise_count)
        outcomes = await dispatch_parallel(premises, self.backend, context=context)
        ho.absorb(outcomes)

        if self.retriever is not None:
            for o in outcomes:
                try:
                    self.retriever.add(
                        f"{o.premise.statement}: {o.result.summary}",
                        {"premise": o.premise.id, "ok": o.result.ok},
                    )
                except Exception:
                    pass
        report(await to_premise_report(outcomes, self.thinker))

    async def _single(self, spec: WorkSpec, ho: Handoff, report) -> None:
        """자가 과업 단건 실행."""
        try:
            res = await self.backend.run(spec)
        except Exception as e:
            res = WorkResult(summary=f"예외: {e}", ok=False)
        outcome = PremiseOutcome(
            premise=Premise(id=spec.premise_id or "task", statement=spec.instruction[:60]),
            result=res,
        )
        ho.absorb([outcome])
        report(await to_premise_report([outcome], self.thinker))
