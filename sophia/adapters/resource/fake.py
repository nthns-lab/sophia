"""FakeResourceGovernor — 테스트용. 고정 스냅샷 + 결정론적 동시성."""
from __future__ import annotations

from ...ports.resource import ResourceGovernor, ResourceSnapshot


class FakeResourceGovernor(ResourceGovernor):
    def __init__(self, cpu=10.0, mem=20.0, load=0.1, force: int | None = None) -> None:
        self._snap = ResourceSnapshot(cpu_percent=cpu, mem_percent=mem, load_per_core=load)
        self.force = force  # 주면 ceiling 무시하고 이 값을 (clamp 후) 반환

    def snapshot(self) -> ResourceSnapshot:
        return self._snap

    def concurrency(self, ceiling: int) -> int:
        if self.force is not None:
            return max(1, min(ceiling, self.force))
        # 부하 낮으면 ceiling, 높으면 1 (system 거버너와 같은 의미의 단순판)
        busy = max(self._snap.cpu_percent, self._snap.mem_percent, self._snap.load_per_core * 100)
        return ceiling if busy < 50 else 1
