"""SOPHIA 포트폴리오 대시보드 TUI (curses, 의존성 0).

왼쪽: 프로젝트 목록(상태·정체·블로커). 오른쪽: 선택 프로젝트 상세 / 다이제스트.
키: ↑↓ 선택 · s 한 스텝 전진(포트폴리오를 한 틱 굴림) · d 다이제스트 토글 · q 종료.

렌더링은 ui/render.py(순수 함수)에, curses 는 여기서 얇게. claude 없이 fake 로 돈다:
  python3 -m sophia.ui.tui
"""
from __future__ import annotations

import asyncio

from ..core.portfolio.portfolio import Portfolio
from . import render


class SophiaTUI:
    def __init__(self, portfolio: Portfolio) -> None:
        self.pf = portfolio
        self.selected = 0
        self.view = "detail"   # detail | digest
        self.status_msg = ""

    def _draw(self, stdscr) -> None:
        import curses

        stdscr.erase()
        h, w = stdscr.getmaxyx()
        now = self.pf._tick
        projects = self.pf.projects
        left_w = max(24, w // 3)

        # 헤더
        header = f" SOPHIA — 포트폴리오 ({len([p for p in projects if p.is_active()])} active / {len(projects)})"
        stdscr.addnstr(0, 0, header.ljust(w), w, curses.A_REVERSE)

        # 왼쪽: 목록
        for i, line in enumerate(render.render_project_list(projects, self.selected, now)):
            if 1 + i >= h - 1:
                break
            attr = curses.A_BOLD if i == self.selected else curses.A_NORMAL
            stdscr.addnstr(1 + i, 0, line.ljust(left_w), left_w, attr)

        # 구분선
        for y in range(1, h - 1):
            stdscr.addch(y, left_w, ord("|"))

        # 오른쪽: 상세 또는 다이제스트
        if self.view == "digest":
            body = render.render_digest(projects, now)
        elif projects:
            body = render.render_detail(projects[self.selected], now)
        else:
            body = ["(프로젝트 없음)"]
        rx = left_w + 2
        for i, line in enumerate(body):
            if 1 + i >= h - 1:
                break
            stdscr.addnstr(1 + i, rx, line, max(1, w - rx - 1))

        # 푸터
        foot = render.render_footer(now, self.view)
        if self.status_msg:
            foot = f"{foot} · {self.status_msg}"
        stdscr.addnstr(h - 1, 0, foot.ljust(w), w, curses.A_REVERSE)
        stdscr.refresh()

    def _loop(self, stdscr) -> None:
        import curses

        curses.curs_set(0)
        stdscr.keypad(True)
        while True:
            self._draw(stdscr)
            ch = stdscr.getch()
            n = len(self.pf.projects)
            if ch in (ord("q"), ord("Q")):
                break
            elif ch in (curses.KEY_UP, ord("k")):
                self.selected = max(0, self.selected - 1)
            elif ch in (curses.KEY_DOWN, ord("j")):
                self.selected = min(max(0, n - 1), self.selected + 1)
            elif ch in (ord("d"), ord("D")):
                self.view = "digest" if self.view == "detail" else "detail"
            elif ch in (ord("s"), ord("S"), ord(" ")):
                advanced = asyncio.run(self.pf.step())
                self.status_msg = "한 스텝 전진" if advanced else "모두 done"
                if self.selected >= n:
                    self.selected = max(0, n - 1)

    def run(self) -> None:
        import curses

        curses.wrapper(self._loop)


def _demo_portfolio() -> Portfolio:
    """claude 없이 도는 데모 포트폴리오 (fake 백엔드)."""
    from ..adapters.fake_worker import FakeWorkerBackend
    from ..adapters.thinker.fake import FakeThinker
    from ..core.loop.scheduler import Scheduler
    from ..core.manager.director import Director
    from ..core.portfolio.project import Blocker, Project

    projects = [
        Project(id="auth", goal="로그인 OAuth 개편", org="본부1",
                pending_requests=["시작"],
                blockers=[Blocker("auth", "OAuth 제공자 구글/카카오 중?", leverage=3)]),
        Project(id="dash", goal="실시간 대시보드", org="본부2",
                pending_requests=["시작"],
                blockers=[Blocker("dash", "색상 테마 승인 필요", leverage=1)]),
        Project(id="etl", goal="데이터 파이프라인", org="지원조직",
                pending_requests=["시작"]),
        Project(id="rag", goal="사내 문서 RAG", org="본부3",
                pending_requests=["시작"],
                blockers=[Blocker("rag", "벡터DB 선택(pgvector vs qdrant)", leverage=2)]),
    ]

    def factory(p: Project) -> Scheduler:
        th = FakeThinker(script=[
            {"premises": [{"id": "a", "statement": f"{p.goal} 접근A", "rationale": "r"}]},
            f"{p.id}: 한 스텝 진행했습니다.",
        ])
        return Scheduler(
            backend=FakeWorkerBackend(), director=Director(goal=p.goal), thinker=th,
            goal=p.goal, handoff_path=f"/tmp/sophia_tui_{p.id}.json", max_cycles=1,
            clock=lambda: 0.0, sleep=lambda s: asyncio.sleep(0),
            pending_requests=list(p.pending_requests),
        )

    return Portfolio(projects=projects, scheduler_factory=factory,
                     digest_interval=3, max_ticks=None)


def main() -> None:
    SophiaTUI(_demo_portfolio()).run()


if __name__ == "__main__":
    main()
