"""SystemResourceGovernor — 실제 하드웨어 부하로 동시 작업량을 조절.

psutil 이 있으면 쓰고, 없으면 os.getloadavg + /proc/meminfo 로 폴백한다.
어느 신호도 못 읽으면 보수적으로 동작(동시성 1)한다 — 측정 실패가 폭주가 되면 안 된다.
"""
from __future__ import annotations

import os

from ...ports.resource import ResourceGovernor, ResourceSnapshot


def _mem_percent_from_proc() -> float:
    try:
        total = avail = None
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    total = float(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    avail = float(line.split()[1])
                if total is not None and avail is not None:
                    break
        if total and avail is not None and total > 0:
            return max(0.0, min(100.0, (1.0 - avail / total) * 100.0))
    except (OSError, ValueError, IndexError):
        pass
    return 0.0


class SystemResourceGovernor(ResourceGovernor):
    def __init__(
        self,
        cpu_high: float = 85.0,    # 이 이상이면 동시성을 깎는다
        mem_high: float = 85.0,
        load_high: float = 1.0,    # per-core loadavg 포화선
    ) -> None:
        self.cpu_high = cpu_high
        self.mem_high = mem_high
        self.load_high = load_high
        self._psutil = None
        try:
            import psutil  # optional

            self._psutil = psutil
            # 첫 호출은 0 을 반환하므로 베이스라인을 깐다(non-blocking)
            psutil.cpu_percent(interval=None)
        except Exception:
            self._psutil = None

    def snapshot(self) -> ResourceSnapshot:
        cpu = mem = 0.0
        if self._psutil is not None:
            try:
                cpu = float(self._psutil.cpu_percent(interval=None))
                mem = float(self._psutil.virtual_memory().percent)
            except Exception:
                cpu = mem = 0.0
        if mem == 0.0:
            mem = _mem_percent_from_proc()

        cores = os.cpu_count() or 1
        try:
            load1 = os.getloadavg()[0]
        except (OSError, AttributeError):
            load1 = 0.0
        return ResourceSnapshot(
            cpu_percent=cpu, mem_percent=mem, load_per_core=load1 / cores
        )

    def concurrency(self, ceiling: int) -> int:
        if ceiling <= 1:
            return max(1, ceiling)
        s = self.snapshot()
        # 가장 압박이 큰 신호를 기준으로 0~1 여유(headroom)를 구한다.
        cpu_head = max(0.0, (self.cpu_high - s.cpu_percent) / self.cpu_high)
        mem_head = max(0.0, (self.mem_high - s.mem_percent) / self.mem_high)
        load_head = max(0.0, (self.load_high - s.load_per_core) / self.load_high)
        headroom = min(cpu_head, mem_head, load_head)
        allowed = round(1 + (ceiling - 1) * headroom)
        return max(1, min(ceiling, allowed))
