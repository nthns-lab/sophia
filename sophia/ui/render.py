"""TUI 렌더링 — 순수 함수만. curses 와 분리해 테스트 가능하게 한다.

각 함수는 Project 리스트/단일 Project 를 받아 '그릴 줄들(list[str])'을 돌려준다.
curses 셸(tui.py)은 이 줄들을 화면에 찍기만 한다.
"""
from __future__ import annotations

from ..core.portfolio.digest import build_digest
from ..core.portfolio.project import Project

_STATUS_MARK = {"active": "▶", "blocked": "⏸", "done": "✓"}


def render_project_list(projects: list[Project], selected: int, now_tick: int) -> list[str]:
    """왼쪽 패널: 프로젝트 목록. 선택행은 '›', 정체는 '!', 블로커 수 표시."""
    lines = []
    for i, p in enumerate(projects):
        cursor = "›" if i == selected else " "
        mark = _STATUS_MARK.get(p.status, "?")
        stale = "!" if (p.is_active() and p.staleness(now_tick) >= 14) else " "
        bl = f" ⚑{len(p.blockers)}" if p.blockers else ""
        org = f"{p.org}/" if p.org else ""
        lines.append(f"{cursor}{stale}{mark} {org}{p.id}{bl}")
    if not lines:
        lines.append("  (프로젝트 없음)")
    return lines


def render_detail(p: Project, now_tick: int) -> list[str]:
    """오른쪽 패널: 선택한 프로젝트 상세."""
    lines = [
        f"■ {p.org + '/' if p.org else ''}{p.id}",
        f"목표: {p.goal}",
        f"상태: {p.status} · {p.cycles_done}사이클 · 정체 {p.staleness(now_tick)}틱",
        "",
    ]
    if p.blockers:
        lines.append(f"결정 대기 ({len(p.blockers)}):")
        for b in sorted(p.blockers, key=lambda x: x.leverage, reverse=True):
            lines.append(f"  ⚑[{b.leverage}] {b.question}")
    else:
        lines.append("결정 대기 없음")
    if p.pending_requests:
        lines.append("")
        lines.append(f"대기 요청 {len(p.pending_requests)} · 선제작업 {len(p.speculative_requests)}")
    return lines


def render_digest(projects: list[Project], now_tick: int, stale_threshold: int = 14) -> list[str]:
    """다이제스트 뷰: 전체 블로커 leverage 순 + 정체 + 현황."""
    return build_digest(projects, now_tick, stale_threshold).split("\n")


def render_footer(now_tick: int, view: str) -> str:
    v = "다이제스트" if view == "digest" else "상세"
    return f" tick {now_tick} · [{v}]  ↑↓ 선택  s 한스텝  d 다이제스트  q 종료 "
