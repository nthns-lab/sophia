"""FakeNotifier — 테스트용. 보낸 보고를 메모리에 모은다."""
from __future__ import annotations

from ...ports.notifier import Notifier


class FakeNotifier(Notifier):
    def __init__(self, fail: bool = False) -> None:
        self.sent: list[dict] = []
        self.fail = fail

    def send(self, subject: str, body: str) -> bool:
        if self.fail:
            return False
        self.sent.append({"subject": subject, "body": body})
        return True
