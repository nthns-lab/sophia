"""NoopRetriever — retrieval 미사용 기본값. 의존성 없이 항상 빈 결과."""
from __future__ import annotations

from typing import Any

from ...ports.retriever import Retriever


class NoopRetriever(Retriever):
    def add(self, text: str, meta: dict[str, Any] | None = None) -> None:
        return None

    def query(self, text: str, k: int = 5) -> list[dict[str, Any]]:
        return []
