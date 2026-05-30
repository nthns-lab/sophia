"""WorkerBackend 포트 — 일꾼(Claude Code / Codex)을 추상화하는 핵심 seam.

내부 로직(core)은 '누구에게 시키는지' 모른 채 이 인터페이스만 본다.
백엔드 의존 코드는 adapters/ 안에서만 산다.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Capabilities:
    worktree_isolation: bool = False
    structured_output: bool = False
    max_context_tokens: int = 200_000
    streaming: bool = False


@dataclass
class WorkSpec:
    """일꾼에게 넘기는 작업 단위."""
    instruction: str
    context: str = ""
    premise_id: str | None = None
    isolation: bool = False
    output_schema: dict[str, Any] | None = None


@dataclass
class WorkResult:
    """일꾼 결과. 핸드오프 스키마(decisions/artifacts)와 같은 모양이라
    변환 없이 reporter·handoff로 흘러든다."""
    summary: str
    ok: bool = True
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    decisions: list[dict[str, Any]] = field(default_factory=list)
    raw_log_ref: str | None = None


class WorkerBackend(ABC):
    @abstractmethod
    def capabilities(self) -> Capabilities: ...

    @abstractmethod
    async def run(self, spec: WorkSpec) -> WorkResult: ...
