import asyncio
import os
import subprocess
from pathlib import Path

from teamlead.adapters.isolation import is_git_repo, worktree


def _init_repo(path: Path) -> str:
    """최소 git repo 생성(worktree add 는 HEAD 커밋이 있어야 함)."""
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    subprocess.run(["git", "init", "-q", str(path)], check=True, env=env)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "t@t.t"], check=True, env=env)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "t"], check=True, env=env)
    (path / "f.txt").write_text("hi", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "."], check=True, env=env)
    subprocess.run(["git", "-C", str(path), "commit", "-q", "-m", "init"], check=True, env=env)
    return str(path)


def test_none_base_yields_none():
    async def go():
        async with worktree(None, "x") as cwd:
            return cwd
    assert asyncio.run(go()) is None


def test_non_git_dir_yields_none(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    async def go():
        async with worktree(str(plain), "x") as cwd:
            return cwd
    assert asyncio.run(go()) is None


def test_is_git_repo(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    assert asyncio.run(is_git_repo(repo)) is True
    assert asyncio.run(is_git_repo(None)) is False


def test_worktree_creates_isolated_cwd_and_cleans_up(tmp_path):
    repo = _init_repo(tmp_path / "repo")
    captured = {}

    async def go():
        async with worktree(repo, "premiseA") as cwd:
            captured["cwd"] = cwd
            # 격리 cwd 가 실재하고 base repo 의 파일(f.txt)이 체크아웃돼 있어야 함
            assert cwd is not None
            assert Path(cwd).is_dir()
            assert (Path(cwd) / "f.txt").exists()
            # 병렬 격리 핵심: base repo 와 다른 경로
            assert Path(cwd).resolve() != Path(repo).resolve()
        return captured["cwd"]

    cwd = asyncio.run(go())
    # 컨텍스트 종료 후 정리됐는지
    assert not Path(cwd).exists()


def test_parallel_worktrees_are_distinct(tmp_path):
    repo = _init_repo(tmp_path / "repo")

    async def go():
        async with worktree(repo, "A") as a, worktree(repo, "B") as b:
            assert a is not None and b is not None
            assert Path(a).resolve() != Path(b).resolve()
            return a, b

    a, b = asyncio.run(go())
    assert not Path(a).exists() and not Path(b).exists()
