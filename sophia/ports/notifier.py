"""Notifier 포트 — 보고를 사람에게 '전달'하는 채널.

소피아의 보고는 stdout 으로 흘리면 휘발한다. 사람은 하루 한 번 이메일을 본다 —
그거면 충분하다. Notifier 는 "어디로 보내는지"를 추상화한다(이메일/stdout/슬랙…).
core 는 send() 만 안다.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class Notifier(ABC):
    @abstractmethod
    def send(self, subject: str, body: str) -> bool:
        """보고를 전달. 성공하면 True. 실패해도 예외 대신 False(6h 루프 보호)."""
        ...
