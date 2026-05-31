"""EmbeddingRetriever — CPU 다국어 임베더 + numpy 브루트포스 코사인.

벡터DB는 이 규모(세션당 수천 벡터)에 과하다 → 인메모리 numpy. 영속이 필요하면
jsonl 로 덤프/로드. sentence-transformers/numpy 는 optional 이라 lazy import.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...ports.retriever import Retriever

DEFAULT_MODEL = "intfloat/multilingual-e5-small"  # 한/영 혼용, CPU 친화


class EmbeddingRetriever(Retriever):
    def __init__(self, model_name: str = DEFAULT_MODEL, persist_path: str | None = None) -> None:
        self.model_name = model_name
        self.persist_path = persist_path
        self._model = None
        self._texts: list[str] = []
        self._metas: list[dict[str, Any]] = []
        self._vecs = None  # numpy 배열 (lazy)
        if persist_path and Path(persist_path).exists():
            self._load()

    def _ensure_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # optional dep

            self._model = SentenceTransformer(self.model_name)
        return self._model

    def _embed(self, texts: list[str]):
        import numpy as np

        vecs = self._ensure_model().encode(texts, normalize_embeddings=True)
        return np.asarray(vecs, dtype="float32")

    def add(self, text: str, meta: dict[str, Any] | None = None) -> None:
        import numpy as np

        vec = self._embed([text])
        self._vecs = vec if self._vecs is None else np.vstack([self._vecs, vec])
        self._texts.append(text)
        self._metas.append(meta or {})
        if self.persist_path:
            self._save()

    def query(self, text: str, k: int = 5) -> list[dict[str, Any]]:
        if self._vecs is None or not self._texts:
            return []
        import numpy as np

        q = self._embed([text])[0]
        scores = self._vecs @ q  # 정규화돼 있어 내적 = 코사인
        idx = np.argsort(-scores)[:k]
        return [
            {"text": self._texts[i], "meta": self._metas[i], "score": float(scores[i])}
            for i in idx
        ]

    def _save(self) -> None:
        rows = [{"text": t, "meta": m} for t, m in zip(self._texts, self._metas)]
        Path(self.persist_path).write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8"
        )

    def _load(self) -> None:
        texts, metas = [], []
        for line in Path(self.persist_path).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            texts.append(r["text"])
            metas.append(r.get("meta", {}))
        if texts:
            self._texts, self._metas = texts, metas
            self._vecs = self._embed(texts)
