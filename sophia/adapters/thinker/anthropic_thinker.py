"""AnthropicThinker — 작은 모델(haiku)로 관리자 메타인지를 싸게 돌린다.

prompt caching 을 system 블록에 걸어 반복 호출 비용을 낮춘다.
`anthropic` 패키지는 optional 이므로 import 는 생성 시점에만 한다.
"""
from __future__ import annotations

from typing import Any

from ...ports.thinker import Thinker

DEFAULT_MODEL = "claude-haiku-4-5-20251001"


class AnthropicThinker(Thinker):
    def __init__(self, model: str = DEFAULT_MODEL, default_system: str = "") -> None:
        from anthropic import AsyncAnthropic  # optional dep

        self._client = AsyncAnthropic()
        self.model = model
        self.default_system = default_system

    async def think(
        self, prompt: str, *, system: str = "", schema: dict[str, Any] | None = None
    ) -> Any:
        sys = system or self.default_system
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}],
        }
        if sys:
            # prompt caching: 반복되는 페르소나 system 을 캐시
            kwargs["system"] = [
                {"type": "text", "text": sys, "cache_control": {"type": "ephemeral"}}
            ]
        if schema is not None:
            kwargs["tools"] = [
                {
                    "name": "respond",
                    "description": "Return the structured result.",
                    "input_schema": schema,
                }
            ]
            kwargs["tool_choice"] = {"type": "tool", "name": "respond"}

        resp = await self._client.messages.create(**kwargs)
        if schema is not None:
            for block in resp.content:
                if block.type == "tool_use":
                    return block.input
            raise RuntimeError("AnthropicThinker: 구조화 응답에 tool_use 없음")
        return "".join(b.text for b in resp.content if b.type == "text")
