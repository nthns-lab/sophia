"""ResourceGovernor 포트 — "한 번에 얼마나 일할지"를 하드웨어가 정하게 한다.

소피아는 멈추지 않고 계속 일을 만든다(반응 시뮬레이션 루프). 그대로 두면 리소스를
무한히 먹으므로, 매 디스패치 전에 현재 부하를 보고 동시 작업 수를 조인다.
core 는 이 포트만 본다 — psutil 이 있든 없든, 측정 방식이 뭐든 모른다.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ResourceSnapshot:
    cpu_percent: float      # 0~100, 최근 사용률
    mem_percent: float      # 0~100, 사용 중 메모리 비율
    load_per_core: float    # loadavg(1m) / cpu_count, 1.0 이면 포화


class ResourceGovernor(ABC):
    @abstractmethod
    def snapshot(self) -> ResourceSnapshot: ...

    @abstractmethod
    def concurrency(self, ceiling: int) -> int:
        """현재 부하에서 허용할 동시 작업 수. 1..ceiling 사이로 클램프."""
        ...
