"""FakeWorkerBackend — 오프라인 테스트/데모용 일꾼. claude 없이 결정론적 결과."""
from __future__ import annotations

import asyncio

from ..ports.worker import Capabilities, WorkerBackend, WorkResult, WorkSpec


class FakeWorkerBackend(WorkerBackend):
    def __init__(self, latency: float = 0.0, fail_on: set[str] | None = None) -> None:
        self.latency = latency
        self.fail_on = fail_on or set()
        self.runs: list[WorkSpec] = []

    def capabilities(self) -> Capabilities:
        return Capabilities(worktree_isolation=True, structured_output=True, streaming=False)

    async def run(self, spec: WorkSpec) -> WorkResult:
        self.runs.append(spec)
        if self.latency:
            await asyncio.sleep(self.latency)
        pid = spec.premise_id or "task"
        if pid in self.fail_on:
            return WorkResult(summary=f"전제 '{pid}' 실행 실패(모의)", ok=False)
        return WorkResult(
            summary=f"전제 '{pid}' 처리 완료(모의)",
            ok=True,
            decisions=[{"statement": spec.instruction[:40], "why": "모의 실행"}],
            artifacts=[{"path": f"out/{pid}.txt", "status": "created"}],
        )
