"""FakeThinker — 오프라인 테스트/데모용. API 키 없이 결정론적으로 동작.

script 큐에 응답을 넣으면 순서대로 반환하고, 비면 schema 모양을 합성한다.
모든 호출은 self.calls 에 기록되어 어서션에 쓰인다.
"""
from __future__ import annotations

from typing import Any

from ...ports.thinker import Thinker


def _synth(schema: dict[str, Any]) -> Any:
    t = schema.get("type")
    if t == "object":
        props = schema.get("properties", {})
        keys = schema.get("required", list(props))
        return {k: _synth(props.get(k, {"type": "string"})) for k in keys}
    if t == "array":
        return [_synth(schema.get("items", {"type": "string"}))]
    if t in ("number", "integer"):
        return 0
    if t == "boolean":
        return False
    return "placeholder"


class FakeThinker(Thinker):
    def __init__(self, script: list[Any] | None = None) -> None:
        self.script = list(script or [])
        self.calls: list[dict[str, Any]] = []

    async def think(
        self, prompt: str, *, system: str = "", schema: dict[str, Any] | None = None
    ) -> Any:
        self.calls.append({"prompt": prompt, "system": system, "schema": schema})
        if self.script:
            return self.script.pop(0)
        if schema is not None:
            return _synth(schema)
        return "(fake) " + prompt[:80]
