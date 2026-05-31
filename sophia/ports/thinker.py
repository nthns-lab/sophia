"""Thinker 포트 — 관리자(sophia) 자신의 '메타인지'를 위한 경량 추론.

WorkerBackend(무거운 위임)와 분리한다: 전제 도출 / 보고 압축 / 자가과업 제안 같은
짧고 잦은 사고는 작은 모델(haiku)로 싸게 돌린다. 사용자가 말한 '작은 모델 호출'.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Thinker(ABC):
    @abstractmethod
    async def think(
        self, prompt: str, *, system: str = "", schema: dict[str, Any] | None = None
    ) -> Any:
        """schema 가 없으면 str, 있으면 schema 모양의 dict 를 반환한다."""
        ...
