from sophia.adapters.resource.fake import FakeResourceGovernor
from sophia.adapters.resource.system import SystemResourceGovernor
from sophia.ports.resource import ResourceGovernor


def test_fake_low_load_uses_ceiling():
    g = FakeResourceGovernor(cpu=10, mem=20, load=0.1)
    assert g.concurrency(4) == 4


def test_fake_high_load_throttles_to_one():
    g = FakeResourceGovernor(cpu=95, mem=20, load=0.1)
    assert g.concurrency(4) == 1


def test_fake_force_overrides_but_clamps():
    g = FakeResourceGovernor(force=3)
    assert g.concurrency(10) == 3
    assert g.concurrency(2) == 2          # ceiling 으로 클램프
    assert FakeResourceGovernor(force=0).concurrency(4) == 1  # 최소 1


def test_system_governor_implements_port_and_clamps():
    g = SystemResourceGovernor()
    assert isinstance(g, ResourceGovernor)
    c = g.concurrency(8)
    assert 1 <= c <= 8                     # 항상 범위 안
    assert g.concurrency(1) == 1           # ceiling 1 이면 1


def test_system_snapshot_fields_present():
    s = SystemResourceGovernor().snapshot()
    assert s.cpu_percent >= 0.0
    assert 0.0 <= s.mem_percent <= 100.0   # 실제 메모리 비율
    assert s.load_per_core >= 0.0


def test_high_thresholds_force_single():
    # 임계를 0 으로 두면 항상 포화로 간주 → 동시성 1
    g = SystemResourceGovernor(cpu_high=0.01, mem_high=0.01, load_high=0.0001)
    assert g.concurrency(8) == 1
