"""일꾼 출력에서 artifacts(건드린 파일) 추출 헬퍼.

claude stream-json 의 tool_use 블록(Write/Edit/...)에서 file_path 를 뽑아
WorkResult.artifacts 로 채운다. core/handoff 가 이 구조(path/status)를 그대로 흡수한다.
도구 이름 → 상태 매핑은 보수적으로: 모르는 도구는 무시(요약만 남김).
"""
from __future__ import annotations

from typing import Any

# 파일을 건드리는 도구 → status. 읽기 전용/검색 도구는 의도적으로 제외.
_TOOL_STATUS = {
    "Write": "created",
    "Edit": "modified",
    "MultiEdit": "modified",
    "NotebookEdit": "modified",
    "str_replace_editor": "modified",
    "str_replace": "modified",
    "create": "created",
}
# 입력에서 파일 경로가 들어오는 키들(도구마다 다름).
_PATH_KEYS = ("file_path", "path", "notebook_path")


def _path_from_input(inp: dict[str, Any]) -> str | None:
    for k in _PATH_KEYS:
        v = inp.get(k)
        if isinstance(v, str) and v:
            return v
    return None


def artifacts_from_tool_uses(tool_uses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """[{name, input}, ...] → [{path, status, tool}, ...] (경로 기준 중복 제거).

    같은 파일을 여러 번 건드리면 마지막 상태로 합치되, created 는 modified 에 덮이지 않는다
    (한 번 만들면 이후 수정해도 '생성'이 핵심 사실).
    """
    by_path: dict[str, dict[str, Any]] = {}
    for tu in tool_uses:
        name = tu.get("name")
        status = _TOOL_STATUS.get(name)
        if status is None:
            continue
        path = _path_from_input(tu.get("input") or {})
        if not path:
            continue
        if path in by_path:
            # created 우선 유지
            if by_path[path]["status"] != "created":
                by_path[path]["status"] = status
        else:
            by_path[path] = {"path": path, "status": status, "tool": name}
    return list(by_path.values())
