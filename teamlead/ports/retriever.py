"""Retriever 포트 — 우리 유일한 차별 기능: 임베딩 기반 가산적 retrieval.

과거 전제/결과/핸드오프를 임베딩해 두고, 새 요청과 유사한 것만 컨텍스트 '맨 뒤'에
끌어와 붙인다(안정 prefix 보존 → 캐시 안 깸). 메인 타임라인은 절대 필터링하지 않는다.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Retriever(ABC):
    @abstractmethod
    def add(self, text: str, meta: dict[str, Any] | None = None) -> None: ...

    @abstractmethod
    def query(self, text: str, k: int = 5) -> list[dict[str, Any]]:
        """[{text, meta, score}, ...] 를 유사도 내림차순으로 반환."""
        ...
