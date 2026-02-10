# src/retrieval/retrieval_llama.py
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import numpy as np
from llama_cpp import Llama  # llama-cpp-python


# ----------------------------
# Logging suppression (stderr)
# ----------------------------
class suppress_stderr:  # noqa: N801
    
    def __enter__(self):
        import os
        import sys

        self._stderr_fd = sys.stderr.fileno()
        self._old_stderr = os.dup(self._stderr_fd)
        self._devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(self._devnull, self._stderr_fd)
        return self

    def __exit__(self, exc_type, exc, tb):
        import os

        os.dup2(self._old_stderr, self._stderr_fd)
        os.close(self._devnull)
        os.close(self._old_stderr)
        return False


# ----------------------------
# Utilities
# ----------------------------
def normalize_text(s: str) -> str:
    s = (s or "").replace("\u00A0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def l2_normalize(v: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    n = float(np.linalg.norm(v))
    if n < eps:
        return v
    return v / n


def cosine_np(a: np.ndarray, b: np.ndarray) -> float:
    # assumes normalized
    return float(a @ b)


# ----------------------------
# Embedder
# ----------------------------
@dataclass
class LlamaEmbedder:
    model_path: str
    n_ctx: int = 8192
    n_threads: int = 8    
    n_gpu_layers: int = 0
    verbose: bool = False

    def __post_init__(self) -> None:
        
        self.llm = Llama(
            model_path=str(self.model_path),
            embedding=True,
            n_ctx=int(self.n_ctx),
            n_threads=int(self.n_threads),
            n_gpu_layers=int(self.n_gpu_layers),
            verbose=bool(self.verbose),  
        )
        
        try:
            with suppress_stderr():
                test = self.llm.create_embedding("test")["data"][0]["embedding"]
            self.dim = int(len(test))
        except Exception:
            self.dim = 1024  
    
    def chunk_by_tokens(
        self,
        text: str,
        *,
        chunk_tokens: int,
        overlap_tokens: int,
    ) -> List[str]:
        
        assert chunk_tokens > 0
        assert 0 <= overlap_tokens < chunk_tokens

        t = normalize_text(text)
        if not t:
            return []

        tokens: List[int] = self.llm.tokenize(t.encode("utf-8"), add_bos=False)
        if not tokens:
            return []

        step = chunk_tokens - overlap_tokens
        out: List[str] = []
        start = 0
        while start < len(tokens):
            window = tokens[start:start + chunk_tokens]
            chunk_bytes = self.llm.detokenize(window)
            chunk = chunk_bytes.decode("utf-8", errors="ignore")
            chunk = normalize_text(chunk)
            if chunk:
                out.append(chunk)
            start += step
        return out

    def embed(self, text: str) -> np.ndarray:
        t = normalize_text(text)
        if not t:
            return np.zeros((self.dim,), dtype=np.float32)

        try:
            with suppress_stderr():
                res = self.llm.create_embedding(t)
            v = np.array(res["data"][0]["embedding"], dtype=np.float32)
            return l2_normalize(v)
        except Exception:
            
            return np.zeros((self.dim,), dtype=np.float32)

    def embed_many(self, texts: List[str]) -> np.ndarray:
        vecs: List[np.ndarray] = []
        for t in texts:
            vecs.append(self.embed(t))
        if not vecs:
            return np.zeros((0, self.dim), dtype=np.float32)
        return np.vstack(vecs)


@dataclass
class LlamaIndex:
    rows: List[dict]        
    embs: np.ndarray        


def build_llama_index(
    *,
    corpus_rows: List[dict],
    embedder: LlamaEmbedder,
    section_id: Optional[str] = None,
    language: Optional[str] = None,
    max_docs: Optional[int] = None,
    # chunking:
    chunk_tokens: int = 256,
    overlap_tokens: int = 64,
    min_chunk_chars: int = 120,
    # index-time dedup:
    dedup_exact: bool = True,
) -> LlamaIndex:
    
    base_rows: List[dict] = []

    for r in corpus_rows:
        sid = (r.get("section_id") or "").strip()
        lang = (r.get("language") or "").strip().lower()

        if section_id and sid != section_id:
            continue
        if language and lang and language.strip().lower() != lang:
            continue

        text = normalize_text(r.get("text") or "")
        if not text:
            continue

        base_rows.append(r)
        if max_docs and len(base_rows) >= int(max_docs):
            break

    chunk_rows: List[dict] = []
    chunk_texts: List[str] = []

    seen_norm: set[str] = set()

    for r in base_rows:
        title = normalize_text(r.get("title") or "")
        text = normalize_text(r.get("text") or "")

        pieces = embedder.chunk_by_tokens(
            text,
            chunk_tokens=int(chunk_tokens),
            overlap_tokens=int(overlap_tokens),
        )

        doc_id = r.get("doc_id")
        sid = r.get("section_id")
        lang = r.get("language")

        for j, piece in enumerate(pieces):
            piece = normalize_text(piece)
            if len(piece) < int(min_chunk_chars):
                continue

            # exact-ish dedup at index time
            if dedup_exact:
                key = piece.lower()
                if key in seen_norm:
                    continue
                seen_norm.add(key)

            
            row = dict(r)
            row["chunk_id"] = j
            row["text_chunk"] = piece  
            
            row["doc_id"] = doc_id
            row["section_id"] = sid
            row["language"] = lang

            chunk_rows.append(row)

            
            if title:
                chunk_texts.append(f"{title}\n{piece}")
            else:
                chunk_texts.append(piece)

    embs = embedder.embed_many(chunk_texts)  
    return LlamaIndex(rows=chunk_rows, embs=embs)

def retrieve_topk_llama_from_index ( # MMR
    *,
    query: str,
    index: LlamaIndex,
    embedder: LlamaEmbedder,
    top_k: int = 7,
    candidate_pool: int = 120,
    max_per_doc: int = 2,
    lambda_mult: float = 0.75,
    return_debug: bool = False,
) -> list[dict] | tuple[list[dict], dict]:
    """
    MMR selection     
    """
    if not index.rows or index.embs.size == 0:
        return [] if not return_debug else ([], {"candidates": [], "selected": [], "lambda_mult": lambda_mult})

    q = embedder.embed(query)           
    scores = index.embs @ q             

    n = scores.shape[0]
    pool = min(int(candidate_pool), n)
    if pool <= 0:
        return [] if not return_debug else ([], {"candidates": [], "selected": [], "lambda_mult": lambda_mult})

    
    cand_idx = np.argpartition(-scores, kth=pool - 1)[:pool]
    cand_idx = cand_idx[np.argsort(-scores[cand_idx])]

    selected_idx: List[int] = []
    selected_vecs: List[np.ndarray] = []
    per_doc: Dict[str, int] = {}
    
    dbg_candidates = [
        {
            "score": float(scores[i]),
            "doc_id": index.rows[int(i)].get("doc_id"),
            "title": (index.rows[int(i)].get("title") or ""),
            "chunk_id": index.rows[int(i)].get("chunk_id"),
        }
        for i in cand_idx[: min(pool, 15)]
    ]

    # жадный MMR
    for _ in range(min(int(top_k), pool)):
        best_i = None
        best_mmr = -1e18

        for i in cand_idx.tolist():
            if i in selected_idx:
                continue

            row = index.rows[int(i)]
            doc_id = str(row.get("doc_id", "unknown_doc"))
            if per_doc.get(doc_id, 0) >= int(max_per_doc):
                continue

            rel = float(scores[int(i)])

            if not selected_vecs:
                mmr = rel
            else:
                v = index.embs[int(i)]
                max_sim_to_selected = max(float(v @ sv) for sv in selected_vecs)
                mmr = float(lambda_mult) * rel - (1.0 - float(lambda_mult)) * max_sim_to_selected

            if mmr > best_mmr:
                best_mmr = mmr
                best_i = int(i)

        if best_i is None:
            break

        selected_idx.append(best_i)
        selected_vecs.append(index.embs[best_i])

        doc_id = str(index.rows[best_i].get("doc_id", "unknown_doc"))
        per_doc[doc_id] = per_doc.get(doc_id, 0) + 1

    out: List[dict] = []
    for i in selected_idx:
        r = dict(index.rows[int(i)])
        r["_score"] = float(scores[int(i)])
        r["text"] = r.get("text_chunk") or r.get("text") or ""
        out.append(r)

    if return_debug:
        dbg_selected = [
            {
                "score": float(scores[i]),
                "doc_id": index.rows[int(i)].get("doc_id"),
                "title": (index.rows[int(i)].get("title") or ""),
                "chunk_id": index.rows[int(i)].get("chunk_id"),
            }
            for i in selected_idx
        ]
        return out, {"candidates": dbg_candidates, "selected": dbg_selected, "lambda_mult": lambda_mult}

    return out
