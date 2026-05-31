"""pytest 없이도 도는 종단 스모크: `python3 scripts/smoke.py`.

전체 흐름(전제 병렬 탐색 → 5문장 보고 → 핸드오프 저장)을 fake 로 검증한다.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sophia.adapters.fake_worker import FakeWorkerBackend  # noqa: E402
from sophia.adapters.thinker.fake import FakeThinker  # noqa: E402
from sophia.core.loop.scheduler import Scheduler  # noqa: E402
from sophia.core.manager.director import Director  # noqa: E402


async def _noop(_):
    return None


def main() -> int:
    thinker = FakeThinker(script=[
        {"premises": [
            {"id": "A", "statement": "최소 기능부터", "rationale": "빠른 검증"},
            {"id": "B", "statement": "안정성 우선", "rationale": "롱런"},
            {"id": "C", "statement": "확장성 우선", "rationale": "멀티 백엔드"},
        ]},
        "세 전제로 병렬 진행해 모두 완료, 확장성안은 보류 후보입니다.",
    ])
    backend = FakeWorkerBackend(fail_on={"C"})
    out_path = "/tmp/sophia_smoke_handoff.json"
    sched = Scheduler(
        backend=backend,
        director=Director(goal="중간관리자 하네스를 만든다"),
        thinker=thinker,
        goal="중간관리자 하네스를 만든다",
        handoff_path=out_path,
        max_cycles=1,
        clock=lambda: 0.0,
        sleep=_noop,
        pending_requests=["하네스를 만들어"],
    )
    reports: list[str] = []
    ho = asyncio.run(sched.run(report=reports.append))

    assert len(backend.runs) == 3, backend.runs
    assert len(ho.decisions) == 2, ho.decisions       # A,B 성공
    assert len(ho.discarded) == 1, ho.discarded       # C 실패 → discarded
    assert reports == ["세 전제로 병렬 진행해 모두 완료, 확장성안은 보류 후보입니다."]
    assert Path(out_path).exists()
    assert ho.status == "done"

    print("SMOKE PASS")
    print("  보고:", reports[0])
    print(f"  핸드오프: decisions={len(ho.decisions)} discarded={len(ho.discarded)} → {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
