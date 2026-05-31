"""StdoutNotifier — 기본값. 이메일 설정이 없을 때 콘솔로 보고. 항상 동작."""
from __future__ import annotations

from typing import Callable

from ...ports.notifier import Notifier


class StdoutNotifier(Notifier):
    def __init__(self, sink: Callable[[str], None] = print) -> None:
        self.sink = sink

    def send(self, subject: str, body: str) -> bool:
        try:
            self.sink(f"\n=== 보고: {subject} ===\n{body}\n")
            return True
        except Exception:
            return False
