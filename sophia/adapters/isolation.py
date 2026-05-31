"""worktree 격리 헬퍼 — 병렬 전제가 서로의 파일을 안 건드리게 한다.

claude/codex 어댑터가 공유한다. base_repo 가 git repo 일 때만 진짜 격리:
각 작업마다 `git worktree add --detach` 로 독립 작업트리를 만들어 cwd 로 주고,
끝나면 `git worktree remove --force` 로 정리한다.

base_repo 가 None 이거나 git repo 가 아니면 격리는 no-op(None cwd) — 정직하게.
무엇을 하든 6h 루프를 죽이지 않도록 모든 git 실패를 삼킨다.
"""
from __future__ import annotations

import asyncio
import contextlib
import tempfile
from pathlib import Path
from typing import AsyncIterator


async def _git(base_repo: str, *args: str) -> tuple[int, str]:
    """`git -C base_repo <args>` 를 실행. (returncode, stderr) 반환."""
    proc = await asyncio.create_subprocess_exec(
        "git", "-C", base_repo, *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    return proc.returncode or 0, stderr.decode("utf-8", "replace")


async def is_git_repo(base_repo: str | None) -> bool:
    if not base_repo:
        return False
    try:
        rc, _ = await _git(base_repo, "rev-parse", "--is-inside-work-tree")
        return rc == 0
    except Exception:
        return False


@contextlib.asynccontextmanager
async def worktree(base_repo: str | None, label: str = "tl") -> AsyncIterator[str | None]:
    """격리 작업트리 cwd 를 yield. 격리 불가 시 None.

    사용: `async with worktree(base, pid) as cwd: ... cwd 에서 일꾼 실행`
    """
    if not await is_git_repo(base_repo):
        yield None
        return

    assert base_repo is not None
    safe = "".join(c if c.isalnum() else "_" for c in label)[:24]
    path = tempfile.mkdtemp(prefix=f"tlwt_{safe}_")
    created = False
    try:
        rc, err = await _git(base_repo, "worktree", "add", "--detach", path)
        if rc != 0:
            # worktree 생성 실패 → 격리 없이 진행(루프는 살아있어야 함)
            with contextlib.suppress(OSError):
                Path(path).rmdir()
            yield None
            return
        created = True
        yield path
    finally:
        if created:
            with contextlib.suppress(Exception):
                await _git(base_repo, "worktree", "remove", "--force", path)
        with contextlib.suppress(Exception):
            # worktree remove 가 디렉토리를 지우지만, 실패 대비 best-effort 정리
            if Path(path).exists():
                import shutil
                shutil.rmtree(path, ignore_errors=True)
