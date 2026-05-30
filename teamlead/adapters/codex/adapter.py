"""Codex 어댑터 — `codex exec` 를 비대화형으로 띄운다. WorkerBackend 포트 검증용.

claude_code 어댑터와 같은 포트(WorkerBackend)를 구현한다 → core 는 둘을 구분하지 못한다.
이게 포트&어댑터 구조의 핵심 증명: 백엔드 교체 = 어댑터 교체.

codex exec 인터페이스(2026 edition):
- `--json`               JSONL 이벤트를 stdout 으로
- `-o/--output-last-message <F>`  최종 어시스턴트 메시지를 파일로 (가장 안정적인 결과 추출)
- `-C/--working-dir <DIR>`        chdir (spec.isolation 격리에 활용)
- `-s/--sandbox <MODE>`           read-only | workspace-write | danger-full-access
- `--skip-git-repo-check`         git repo 밖에서도 실행 허용

견고성(claude 어댑터와 동일): communicate() 로 stdout/stderr 동시 배수(파이프 deadlock 방지),
start_new_session + killpg 로 타임아웃 시 손자까지 정리, 기본 타임아웃 30분.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import signal
import tempfile

from ...ports.worker import Capabilities, WorkerBackend, WorkResult, WorkSpec
from ..isolation import worktree

DEFAULT_TIMEOUT_S = 30 * 60


class CodexBackend(WorkerBackend):
    def __init__(
        self,
        codex_bin: str = "codex",
        sandbox: str = "workspace-write",
        model: str | None = None,
        working_dir: str | None = None,
        base_repo: str | None = None,
        extra_args: list[str] | None = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        self.codex_bin = codex_bin
        self.sandbox = sandbox
        self.model = model
        self.working_dir = working_dir  # 고정 cwd (격리 아님)
        self.base_repo = base_repo      # git repo 면 전제별 worktree 격리
        self.extra_args = extra_args or []
        self.timeout_s = timeout_s

    def capabilities(self) -> Capabilities:
        return Capabilities(
            worktree_isolation=bool(self.base_repo),  # base_repo 있을 때만 진짜 격리
            structured_output=False,
            max_context_tokens=200_000,
            streaming=True,
        )

    async def run(self, spec: WorkSpec) -> WorkResult:
        if shutil.which(self.codex_bin) is None:
            return WorkResult(summary=f"'{self.codex_bin}' 실행파일을 찾을 수 없음", ok=False)

        # 최종 메시지를 파일로 받는다(JSONL 파싱보다 안정적).
        out_fd, out_path = tempfile.mkstemp(prefix="codex_out_", suffix=".txt")
        os.close(out_fd)

        repo = self.base_repo if spec.isolation else None
        async with worktree(repo, spec.premise_id or "task") as wt:
            cwd = wt or self.working_dir  # 격리 cwd 우선, 없으면 고정 working_dir
            argv = [
                self.codex_bin,
                "exec",
                "--json",
                "--skip-git-repo-check",
                "-s",
                self.sandbox,
                "-o",
                out_path,
            ]
            if self.model:
                argv += ["-m", self.model]
            if cwd:
                argv += ["-C", cwd]
            argv += [*self.extra_args, self._compose_prompt(spec)]

            try:
                proc = await asyncio.create_subprocess_exec(
                    *argv,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    start_new_session=True,
                )
            except Exception as e:
                self._cleanup(out_path)
                return WorkResult(summary=f"codex 실행 실패: {e}", ok=False)

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=self.timeout_s
                )
            except (asyncio.TimeoutError, TimeoutError):
                await self._terminate_group(proc)
                self._cleanup(out_path)
                return WorkResult(summary=f"타임아웃 {self.timeout_s}s 초과", ok=False)

        final_msg = self._read_output(out_path)
        self._cleanup(out_path)
        return self._parse(final_msg, stdout, stderr, proc.returncode)

    def _compose_prompt(self, spec: WorkSpec) -> str:
        if spec.context:
            return f"{spec.context}\n\n---\n\n{spec.instruction}"
        return spec.instruction

    @staticmethod
    def _read_output(path: str) -> str:
        try:
            with open(path, encoding="utf-8") as f:
                return f.read().strip()
        except OSError:
            return ""

    @staticmethod
    def _cleanup(path: str) -> None:
        try:
            os.unlink(path)
        except OSError:
            pass

    @staticmethod
    async def _terminate_group(proc) -> None:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            proc.kill()
        except Exception:
            pass
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except Exception:
            pass

    def _parse(
        self, final_msg: str, stdout: bytes, stderr: bytes, returncode: int | None
    ) -> WorkResult:
        # 1순위: -o 최종 메시지. 2순위: JSONL 이벤트에서 텍스트. 3순위: stderr.
        summary = final_msg
        if not summary:
            summary = self._extract_from_jsonl(stdout)
        if not summary:
            err = stderr.decode("utf-8", "replace").strip()
            summary = f"(no result) {err[:200]}" if err else "(no result)"
        return WorkResult(summary=summary, ok=returncode == 0)

    @staticmethod
    def _extract_from_jsonl(stdout: bytes) -> str:
        texts: list[str] = []
        for raw in stdout.splitlines():
            line = raw.decode("utf-8", "replace").strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            # codex 이벤트 스키마는 버전마다 다를 수 있어 흔한 키를 관대하게 탐색.
            for key in ("message", "text", "content", "delta"):
                v = ev.get(key) if isinstance(ev, dict) else None
                if isinstance(v, str):
                    texts.append(v)
        return "".join(texts).strip()
