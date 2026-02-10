from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


def read_jsonl(path: Path) -> List[dict]:
    out = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def l2_normalize_rows(mat: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    # mat: [N, D]
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms = np.maximum(norms, eps)
    return mat / norms


@dataclass
class DenseIndex:
    embs: np.ndarray                 # [N, D], float32, L2-normalized
    meta: List[dict]                 # len N
    dim: int

    @classmethod
    def load(cls, npy_path: Path, meta_path: Path, *, normalize: bool = True) -> "DenseIndex":
        if not npy_path.exists():
            raise FileNotFoundError(npy_path)
        if not meta_path.exists():
            raise FileNotFoundError(meta_path)

        embs = np.load(npy_path)
        if embs.dtype != np.float32:
            embs = embs.astype(np.float32)

        meta = read_jsonl(meta_path)
        if embs.shape[0] != len(meta):
            raise RuntimeError(
                f"embs rows != meta rows: {embs.shape[0]} != {len(meta)} "
                f"({npy_path} vs {meta_path})"
            )

        if normalize:
            embs = l2_normalize_rows(embs)

        return cls(embs=embs, meta=meta, dim=int(embs.shape[1]))


class DenseRetriever:
    """
    Быстрый retriever по готовым эмбеддингам.
    Требует query_emb уже L2-нормализованный (или нормализует сам).
    """
    def __init__(self, index: DenseIndex):
        self.index = index

    def search(
        self,
        query_emb: np.ndarray,
        *,
        top_k: int = 10,
        section_id: Optional[str] = None,
        language: Optional[str] = None,
    ) -> List[Tuple[int, float]]:
        q = query_emb.astype(np.float32)
        # L2 norm query
        qn = float(np.linalg.norm(q))
        if qn > 1e-12:
            q = q / qn

        # cosine(a,b) = dot(a,b) если оба L2-норм
        scores = self.index.embs @ q  # [N]

        # фильтры (не обязательны, но полезны)
        if section_id or language:
            mask = np.ones(scores.shape[0], dtype=bool)
            if section_id:
                sid = section_id.strip()
                mask &= np.array([(m.get("section_id") or "").strip() == sid for m in self.index.meta], dtype=bool)
            if language:
                lang = language.strip().lower()
                mask &= np.array([(m.get("language") or "").strip().lower() == lang for m in self.index.meta], dtype=bool)

            idxs = np.where(mask)[0]
            if idxs.size == 0:
                return []
            sub_scores = scores[idxs]
            k = min(int(top_k), int(sub_scores.size))
            top_local = np.argpartition(-sub_scores, kth=k-1)[:k]
            top_local = top_local[np.argsort(-sub_scores[top_local])]
            return [(int(idxs[i]), float(sub_scores[i])) for i in top_local]

        k = min(int(top_k), int(scores.size))
        top = np.argpartition(-scores, kth=k-1)[:k]
        top = top[np.argsort(-scores[top])]
        return [(int(i), float(scores[i])) for i in top]
