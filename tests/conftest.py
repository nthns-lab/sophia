"""테스트용 결정론 도구: 고정 시계 + no-op sleep.

스케줄러 종료는 max_cycles 로 통제하므로 시계는 '항상 0'으로 둬서
시간 경계가 절대 먼저 끊지 않게 한다(틱 의존성 제거).
"""
from __future__ import annotations


def zero_clock() -> float:
    return 0.0


async def noop_sleep(_seconds: float) -> None:
    return None
