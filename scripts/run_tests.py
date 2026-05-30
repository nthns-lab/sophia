"""pytest 없는 환경용 무의존 테스트 러너: `python3 scripts/run_tests.py`.

tests/ 의 test_*.py 를 import 해 test_* 함수를 실행한다.
`tmp_path` 인자가 있으면 tempfile 로 임시 디렉토리(Path)를 주입한다.
pytest 가 있으면 그냥 `python3 -m pytest` 를 쓰면 된다 — 이건 폴백.
"""
from __future__ import annotations

import importlib.util
import inspect
import tempfile
import traceback
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# tests 를 패키지로 인식시킨다 (상대 import 지원)
import importlib

tests_pkg = importlib.util.module_from_spec(
    importlib.util.spec_from_loader("tests", loader=None)
)
tests_pkg.__path__ = [str(ROOT / "tests")]  # type: ignore[attr-defined]
sys.modules["tests"] = tests_pkg


def _load(path: Path):
    # tests 를 패키지로 로드해야 test 파일의 `from .conftest import ...` 가 동작한다.
    mod_name = f"tests.{path.stem}"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def main() -> int:
    test_files = sorted((ROOT / "tests").glob("test_*.py"))
    passed = failed = 0
    failures: list[str] = []

    for tf in test_files:
        mod = _load(tf)
        for name, fn in inspect.getmembers(mod, inspect.isfunction):
            if not name.startswith("test_"):
                continue
            if getattr(fn, "__module__", None) != mod.__name__:
                continue  # import 된 헬퍼 제외
            kwargs = {}
            if "tmp_path" in inspect.signature(fn).parameters:
                kwargs["tmp_path"] = Path(tempfile.mkdtemp(prefix="tl_"))
            try:
                fn(**kwargs)
                passed += 1
                print(f"  PASS {tf.stem}::{name}")
            except Exception:
                failed += 1
                failures.append(f"{tf.stem}::{name}\n{traceback.format_exc()}")
                print(f"  FAIL {tf.stem}::{name}")

    print(f"\n{passed} passed, {failed} failed")
    if failures:
        print("\n===== FAILURES =====")
        for f in failures:
            print(f)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
