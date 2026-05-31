import asyncio
import os

from sophia.adapters.fake_worker import FakeWorkerBackend
from sophia.adapters.notifier.email_smtp import EmailNotifier
from sophia.adapters.notifier.fake import FakeNotifier
from sophia.adapters.notifier.stdout import StdoutNotifier
from sophia.adapters.thinker.fake import FakeThinker
from sophia.core.loop.scheduler import Scheduler
from sophia.core.manager.director import Director

from .conftest import noop_sleep, zero_clock


def test_stdout_notifier_sends():
    captured = []
    n = StdoutNotifier(sink=captured.append)
    assert n.send("제목", "본문") is True
    assert "제목" in captured[0] and "본문" in captured[0]


def test_fake_notifier_collects():
    n = FakeNotifier()
    n.send("s1", "b1")
    assert n.sent == [{"subject": "s1", "body": "b1"}]


def test_fake_notifier_failure_returns_false():
    assert FakeNotifier(fail=True).send("s", "b") is False


def test_email_from_env_none_without_config(monkeypatch=None):
    # 설정 없으면 None (caller 가 폴백) — 환경변수 비우고 확인
    for k in ("SOPHIA_SMTP_HOST", "SOPHIA_MAIL_TO"):
        os.environ.pop(k, None)
    assert EmailNotifier.from_env() is None


def test_email_builds_and_sends_via_injected_sender():
    sent = {}
    def fake_send(msg):
        sent["subject"] = msg["Subject"]
        sent["to"] = msg["To"]
        sent["body"] = msg.get_content()
    n = EmailNotifier(host="h", port=587, user="u", password="p",
                      mail_from="a@a", mail_to="b@b", sender=fake_send)
    assert n.send("제목", "본문") is True
    assert sent["subject"] == "제목" and sent["to"] == "b@b"
    assert "본문" in sent["body"]


def test_email_send_failure_returns_false():
    def boom(msg):
        raise OSError("smtp down")
    n = EmailNotifier(host="h", port=587, user="u", password="p",
                      mail_from="a@a", mail_to="b@b", sender=boom)
    assert n.send("s", "b") is False


def test_scheduler_sends_reports_to_notifier(tmp_path):
    notifier = FakeNotifier()
    thinker = FakeThinker(script=[
        {"premises": [{"id": "a", "statement": "A", "rationale": "r"}]},
        "전제 A로 완료했습니다.",
    ])
    sched = Scheduler(
        backend=FakeWorkerBackend(), director=Director(goal="목표X", insights=["인사이트Y"]),
        thinker=thinker, goal="목표X", handoff_path=str(tmp_path / "h.json"),
        max_cycles=1, clock=zero_clock, sleep=noop_sleep, pending_requests=["요청"],
        notifier=notifier,
    )
    asyncio.run(sched.run(report=lambda _m: None))
    bodies = [m["body"] for m in notifier.sent]
    assert "인사이트Y" in bodies
    assert "전제 A로 완료했습니다." in bodies
    assert all(m["subject"].startswith("[SOPHIA]") for m in notifier.sent)
    assert any("목표X" in m["subject"] for m in notifier.sent)


def test_notifier_failure_does_not_kill_loop(tmp_path):
    thinker = FakeThinker(script=[
        {"premises": [{"id": "a", "statement": "A", "rationale": "r"}]}, "보고",
    ])
    sched = Scheduler(
        backend=FakeWorkerBackend(), director=Director(goal="g"), thinker=thinker, goal="g",
        handoff_path=str(tmp_path / "h.json"), max_cycles=1,
        clock=zero_clock, sleep=noop_sleep, pending_requests=["요청"],
        notifier=FakeNotifier(fail=True),
    )
    ho = asyncio.run(sched.run(report=lambda _m: None))
    assert ho.status == "done"  # 발송 실패해도 정상 종료
