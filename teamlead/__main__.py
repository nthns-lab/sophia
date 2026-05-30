"""엔트리포인트 — 조각들을 와이어링. `python -m teamlead [--real]`.

기본은 오프라인(fake) 데모: API 키/claude 없이 전체 흐름을 보여준다.
--real 은 ClaudeCodeBackend + AnthropicThinker 로 실제 동작.
"""
from __future__ import annotations

import argparse
import asyncio

from .core.loop.scheduler import Scheduler
from .core.manager.director import Director


def build_offline(goal: str) -> Scheduler:
    from .adapters.fake_worker import FakeWorkerBackend
    from .adapters.thinker.fake import FakeThinker

    thinker = FakeThinker(
        script=[
            {  # 전제 3개
                "premises": [
                    {"id": "A", "statement": f"{goal} — 최소 기능부터", "rationale": "빠른 검증"},
                    {"id": "B", "statement": f"{goal} — 안정성 우선", "rationale": "롱런 신뢰성"},
                    {"id": "C", "statement": f"{goal} — 확장성 우선", "rationale": "멀티 백엔드"},
                ]
            },
            "세 전제(최소기능/안정성/확장성)로 병렬 진행했고 모두 모의 완료, 확장성안만 보류 후보입니다.",
        ]
    )
    director = Director(goal=goal, monitor_targets=["LLM 컨텍스트 엔지니어링"])
    return Scheduler(
        backend=FakeWorkerBackend(),
        director=director,
        thinker=thinker,
        goal=goal,
        session_id="offline-demo",
        handoff_path="handoff.json",
        max_runtime_s=3600,
        max_cycles=1,  # 데모는 요청 1건만 — 결정론적(스크립트 소진 후 fake 에코 방지)
        idle_sleep_s=0.05,
        pending_requests=[goal],
    )


def _build_thinker(name: str):
    """thinker 선택. 'claude-cli'(기본)는 pip 없이 claude CLI 로 돈다.
    'anthropic'은 SDK 필요. 'auto'는 anthropic 우선·실패 시 claude-cli 폴백."""
    if name == "anthropic":
        from .adapters.thinker.anthropic_thinker import AnthropicThinker
        return AnthropicThinker()
    if name == "auto":
        try:
            from .adapters.thinker.anthropic_thinker import AnthropicThinker
            return AnthropicThinker()
        except Exception:
            from .adapters.thinker.claude_cli import ClaudeCliThinker
            return ClaudeCliThinker()
    from .adapters.thinker.claude_cli import ClaudeCliThinker
    return ClaudeCliThinker()


def build_real(goal: str, backend_name: str = "claude", thinker_name: str = "claude-cli") -> Scheduler:
    if backend_name == "codex":
        from .adapters.codex.adapter import CodexBackend

        backend = CodexBackend()
    else:
        from .adapters.claude_code.adapter import ClaudeCodeBackend

        backend = ClaudeCodeBackend()

    director = Director(goal=goal, monitor_targets=["LLM 컨텍스트 엔지니어링"])
    return Scheduler(
        backend=backend,
        director=director,
        thinker=_build_thinker(thinker_name),
        goal=goal,
        session_id="run",
        pending_requests=[goal],
    )


def main() -> None:
    ap = argparse.ArgumentParser(prog="teamlead")
    ap.add_argument("--real", action="store_true", help="실제 일꾼 백엔드 + Anthropic 사용")
    ap.add_argument("--backend", choices=["claude", "codex"], default="claude",
                    help="--real 일 때 일꾼 백엔드 선택 (포트가 같아 교체만 하면 됨)")
    ap.add_argument("--thinker", choices=["claude-cli", "anthropic", "auto"], default="claude-cli",
                    help="관리자 메타인지 백엔드. claude-cli=pip 불필요(기본), anthropic=SDK 필요")
    ap.add_argument("--goal", default="데모 목표: 무언가를 만든다")
    args = ap.parse_args()

    sched = (build_real(args.goal, args.backend, args.thinker)
             if args.real else build_offline(args.goal))
    ho = asyncio.run(sched.run())
    print(f"\n[handoff] status={ho.status} decisions={len(ho.decisions)} discarded={len(ho.discarded)}")


if __name__ == "__main__":
    main()
