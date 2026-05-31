"""EmailNotifier — SMTP 로 보고를 이메일 발송. "하루 한 번 이메일 확인" 모델의 채널.

환경변수로 설정(코드에 비밀 안 박음):
  SOPHIA_SMTP_HOST, SOPHIA_SMTP_PORT(기본 587), SOPHIA_SMTP_USER,
  SOPHIA_SMTP_PASS, SOPHIA_MAIL_FROM, SOPHIA_MAIL_TO
설정이 비면 from_env() 가 None 을 돌려준다 → caller 가 StdoutNotifier 로 폴백.
발송 실패는 예외 대신 False(6h 루프를 죽이지 않는다).
"""
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage

from ...ports.notifier import Notifier


class EmailNotifier(Notifier):
    def __init__(self, host, port, user, password, mail_from, mail_to,
                 use_tls=True, sender=None):
        self.host = host
        self.port = int(port)
        self.user = user
        self.password = password
        self.mail_from = mail_from
        self.mail_to = mail_to
        self.use_tls = use_tls
        self._send = sender or self._smtp_send  # 테스트 주입용

    @classmethod
    def from_env(cls) -> "EmailNotifier | None":
        host = os.environ.get("SOPHIA_SMTP_HOST")
        mail_to = os.environ.get("SOPHIA_MAIL_TO")
        if not host or not mail_to:
            return None  # 설정 없음 → caller 가 폴백
        return cls(
            host=host,
            port=os.environ.get("SOPHIA_SMTP_PORT", 587),
            user=os.environ.get("SOPHIA_SMTP_USER", ""),
            password=os.environ.get("SOPHIA_SMTP_PASS", ""),
            mail_from=os.environ.get("SOPHIA_MAIL_FROM", os.environ.get("SOPHIA_SMTP_USER", "")),
            mail_to=mail_to,
        )

    def _build(self, subject: str, body: str) -> EmailMessage:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.mail_from
        msg["To"] = self.mail_to
        msg.set_content(body)
        return msg

    def _smtp_send(self, msg: EmailMessage) -> None:
        with smtplib.SMTP(self.host, self.port, timeout=30) as s:
            if self.use_tls:
                s.starttls()
            if self.user:
                s.login(self.user, self.password)
            s.send_message(msg)

    def send(self, subject: str, body: str) -> bool:
        try:
            self._send(self._build(subject, body))
            return True
        except Exception:
            return False  # 발송 실패가 루프를 멈추지 않게
