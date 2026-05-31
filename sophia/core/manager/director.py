"""Director — 중간관리자 두뇌.

핵심 원칙: 할일이 없으면 만들어서라도 굴린다 (팀장은 본부장 지시 없어도 안 논다).
- next_task(): 큐에 있는 리서치/모니터링을 단건 작업으로 변환
- replenish(): 큐가 비면 thinker 로 새 자가 과업을 생성 → 절대 idle 로 죽지 않음
전제 병렬 탐색(사용자 요청)은 Scheduler.pending_requests 가 담당한다.

리뷰 반영:
- monitor_targets 는 라운드로빈으로 순회한다(매 사이클 [0]만 반복하던 버그).
- 모니터링만 남으면 cooldown 사이클에는 None 을 반환해 루프가 잠들게 한다(스핀 방지).
- replenish 는 이미 본 주제를 걸러내고 큐 상한을 둔다(6h 무한증가 방지).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ...ports.thinker import Thinker
from ...ports.worker import WorkSpec
from ...prompts import templates

MAX_RESEARCH_QUEUE = 50  # 자가과업 큐 상한


@dataclass
class Director:
    goal: str = ""
    insights: list[str] = field(default_factory=list)         # 사용자에게 표면화 대기
    research_topics: list[str] = field(default_factory=list)  # 관련 분야 리서치
    monitor_targets: list[str] = field(default_factory=list)  # 무관 분야 모니터링
    monitor_cooldown: int = 5  # 모니터링만 있을 때 이 사이클마다 1번만 발행
    _monitor_idx: int = 0
    _monitor_tick: int = 0
    _seen_topics: set[str] = field(default_factory=set)

    def drain_insights(self) -> list[str]:
        out, self.insights = self.insights, []
        return out

    def has_work(self) -> bool:
        # 모니터링은 '항상 일감'으로 치지 않는다 — cooldown 사이클엔 쉬게.
        return bool(self.research_topics)

    def next_task(self) -> WorkSpec | None:
        """단건 자가 과업. 리서치 우선, 그다음 모니터링(라운드로빈 + cooldown)."""
        if self.research_topics:
            t = self.research_topics.pop(0)
            return WorkSpec(instruction=templates.WORKER_RESEARCH.format(topic=t))
        if self.monitor_targets:
            self._monitor_tick += 1
            if self._monitor_tick % self.monitor_cooldown != 0:
                return None  # cooldown → 루프가 잠시 쉰다
            m = self.monitor_targets[self._monitor_idx % len(self.monitor_targets)]
            self._monitor_idx += 1
            return WorkSpec(instruction=templates.WORKER_MONITOR.format(target=m))
        return None

    async def replenish(self, thinker: Thinker) -> int:
        """큐가 비면 새 리서치 주제를 자가 생성. 중복/상한 적용. 추가 개수 반환."""
        if len(self.research_topics) >= MAX_RESEARCH_QUEUE:
            return 0
        try:
            out = await thinker.think(
                templates.IDLE_PROPOSE.format(goal=self.goal or "(목표 미설정)"),
                system=templates.SYSTEM_MANAGER,
                schema=templates.IDLE_SCHEMA,
            )
            topics = [t for t in out.get("topics", []) if t]
        except Exception:
            topics = []
        fresh = [t for t in topics if t not in self._seen_topics]
        for t in fresh:
            self._seen_topics.add(t)
        room = MAX_RESEARCH_QUEUE - len(self.research_topics)
        fresh = fresh[:room]
        self.research_topics.extend(fresh)
        return len(fresh)
