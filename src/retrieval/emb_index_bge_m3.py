# src/retrieval/emb_index_bge_m3.py
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


# ----------------------------
# stderr suppression (optional)
# ----------------------------
@contextlib.contextmanager
def suppress_stderr(enabled: bool):
    if not enabled:
        yield
        return
    old = sys.stderr
    try:
        with open(os.devnull, "w") as devnull:
            sys.stderr = devnull
            yield
    finally:
        sys.stderr = old


# ----------------------------
# IO
# ----------------------------
def read_jsonl(path: Path) -> List[dict]:
    out: List[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def write_jsonl(path: Path, rows: List[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


# ----------------------------
# Text helpers
# ----------------------------
def make_doc_text(r: dict) -> str:
    # ВАЖНО: эмбеддинги любят "чистый" контент; заголовок полезен как сигнал.
    title = (r.get("title") or "").strip()
    text = (r.get("text") or "").strip()
    if title and text:
        return f"{title}\n{text}"
    return title or text


def l2_normalize(vec: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    n = float(np.linalg.norm(vec))
    if n < eps:
        return vec * 0.0
    return vec / n


def mean_pool_normalized(vectors: List[np.ndarray]) -> np.ndarray:
    if not vectors:
        return np.zeros((0,), dtype=np.float32)
    m = np.mean(np.stack(vectors, axis=0), axis=0)
    return l2_normalize(m.astype(np.float32))


# ----------------------------
# Chunking by tokens (llama.cpp tokenizer)
# ----------------------------
def chunk_by_tokens(
    llm,
    text: str,
    *,
    max_tokens: int,
    overlap: int,
) -> List[Tuple[int, int, str]]:
    """
    Возвращает список чанков: (start_tok, end_tok, chunk_text)

    Делается через llm.tokenize + llm.detokenize, чтобы границы были токен-совместимы.
    """
    if not text:
        return []

    # llama_cpp.tokenize ожидает bytes
    toks: List[int] = llm.tokenize(text.encode("utf-8"), add_bos=False)
    if not toks:
        return []

    mt = max(16, int(max_tokens))
    ov = max(0, int(overlap))
    if ov >= mt:
        ov = max(0, mt // 4)

    chunks: List[Tuple[int, int, str]] = []
    start = 0
    while start < len(toks):
        end = min(len(toks), start + mt)
        sub = toks[start:end]
        chunk_text = llm.detokenize(sub).decode("utf-8", errors="ignore").strip()
        if chunk_text:
            chunks.append((start, end, chunk_text))
        if end >= len(toks):
            break
        start = max(0, end - ov)

    return chunks


# ----------------------------
# LlamaCpp Embedder
# ----------------------------
@dataclass
class LlamaEmbedConfig:
    model_path: Path
    n_ctx: int = 4096
    n_threads: int = 8
    n_gpu_layers: int = 0
    verbose: bool = False
    suppress_llama_stderr: bool = True


class LlamaCppEmbedder:
    def __init__(self, cfg: LlamaEmbedConfig):
        from llama_cpp import Llama  # type: ignore

        self.cfg = cfg
        self.model = Llama(
            model_path=str(cfg.model_path),
            embedding=True,
            n_ctx=int(cfg.n_ctx),
            n_threads=int(cfg.n_threads),
            n_gpu_layers=int(cfg.n_gpu_layers),
            verbose=bool(cfg.verbose),
        )

    def embed_one(self, text: str) -> np.ndarray:
        with suppress_stderr(self.cfg.suppress_llama_stderr):
            resp = self.model.create_embedding(text or "")
        emb = resp["data"][0]["embedding"]
        v = np.asarray(emb, dtype=np.float32)
        return l2_normalize(v)

    def embed_many(self, texts: List[str], *, log_every: int = 50) -> List[np.ndarray]:
        out: List[np.ndarray] = []
        t0 = time.time()
        for i, t in enumerate(texts, start=1):
            out.append(self.embed_one(t))
            if log_every > 0 and i % log_every == 0:
                dt = time.time() - t0
                print(f"DEBUG: embedded {i}/{len(texts)} chunks ({i/dt:.2f} chunks/s)")
        return out


# ----------------------------
# Main
# ----------------------------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=str, default="data/corpus_sections.jsonl")

    # output
    ap.add_argument("--out_dir", type=str, default="debug/emb_index_bge_m3")
    ap.add_argument("--prefix", type=str, default="bge_m3")

    # filters (optional)
    ap.add_argument("--sections", type=str, default="",
                    help="comma-separated section_id to include (empty = all)")
    ap.add_argument("--language", type=str, default="",
                    help="filter by language exact match, e.g. ru or en (empty = all)")

    # llama embed config
    ap.add_argument("--model", type=str, required=True, help="path to GGUF embedding model (e.g., bge-m3-q4_k_m.gguf)")
    ap.add_argument("--n_ctx", type=int, default=4096)
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--gpu_layers", type=int, default=0)
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--no_suppress_stderr", action="store_true", help="show llama.cpp stderr")

    # chunking
    ap.add_argument("--chunk_tokens", type=int, default=256)
    ap.add_argument("--chunk_overlap", type=int, default=64)

    args = ap.parse_args()

    corpus_path = Path(args.corpus)
    if not corpus_path.exists():
        print(f"ERROR: corpus not found: {corpus_path}")
        return 2

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    model_path = Path(args.model)
    if not model_path.exists():
        print(f"ERROR: model not found: {model_path}")
        return 2

    section_filter = [s.strip() for s in (args.sections or "").split(",") if s.strip()]
    lang_filter = (args.language or "").strip().lower()

    corpus = read_jsonl(corpus_path)

    # apply filters
    rows: List[dict] = []
    for r in corpus:
        sid = (r.get("section_id") or "").strip()
        if not sid:
            continue
        if section_filter and sid not in section_filter:
            continue
        lang = (r.get("language") or "").strip().lower()
        if lang_filter and lang != lang_filter:
            continue
        rows.append(r)

    if not rows:
        print("ERROR: no rows after filters")
        return 2

    print(f"Docs selected: {len(rows)} (from {len(corpus)})")
    print(f"Chunking: chunk_tokens={args.chunk_tokens} overlap={args.chunk_overlap}")

    cfg = LlamaEmbedConfig(
        model_path=model_path,
        n_ctx=int(args.n_ctx),
        n_threads=int(args.threads),
        n_gpu_layers=int(args.gpu_layers),
        verbose=bool(args.verbose),
        suppress_llama_stderr=(not args.no_suppress_stderr),
    )
    embedder = LlamaCppEmbedder(cfg)

    # build chunks
    chunk_texts: List[str] = []
    chunks_meta: List[dict] = []

    # doc-level aggregation bookkeeping
    doc_to_chunk_indices: List[List[int]] = []

    for doc_i, r in enumerate(rows):
        doc_text = make_doc_text(r)
        chunks = chunk_by_tokens(
            embedder.model,
            doc_text,
            max_tokens=int(args.chunk_tokens),
            overlap=int(args.chunk_overlap),
        )
        if not chunks:
            doc_to_chunk_indices.append([])
            continue

        chunk_ids: List[int] = []
        for (st, en, ch_text) in chunks:
            idx = len(chunk_texts)
            chunk_ids.append(idx)

            chunk_texts.append(ch_text)
            chunks_meta.append({
                "chunk_index": idx,
                "doc_index": doc_i,
                "section_id": (r.get("section_id") or "").strip(),
                "language": (r.get("language") or "").strip().lower(),
                "title": (r.get("title") or "").strip(),
                # полезно для дебага/выравнивания
                "tok_start": int(st),
                "tok_end": int(en),
                "text_preview": ch_text[:160],
                # если у тебя есть поля contract_id/source_path — сохраняем, если нет, ок
                "contract_id": r.get("contract_id", ""),
                "source_file": r.get("source_file", r.get("source_path", "")),
            })

        doc_to_chunk_indices.append(chunk_ids)

    if not chunk_texts:
        print("ERROR: no chunks produced (empty texts?)")
        return 2

    print(f"Total chunks: {len(chunk_texts)}")
    print("DEBUG: computing chunk embeddings...")

    # embeddings for chunks
    t0 = time.time()
    chunk_embs_list = embedder.embed_many(chunk_texts, log_every=50)
    dt = time.time() - t0

    dim = int(chunk_embs_list[0].shape[0]) if chunk_embs_list else 0
    print(f"DEBUG: chunk embeddings ready. dim={dim} time={dt:.1f}s")

    chunk_embs = np.stack(chunk_embs_list, axis=0).astype(np.float32)  # [num_chunks, dim]

    # doc embeddings (mean pool of normalized chunk vectors)
    docs_meta: List[dict] = []
    doc_embs_list: List[np.ndarray] = []

    for doc_i, r in enumerate(rows):
        idxs = doc_to_chunk_indices[doc_i]
        vecs = [chunk_embs_list[j] for j in idxs] if idxs else []
        doc_vec = mean_pool_normalized(vecs) if vecs else np.zeros((dim,), dtype=np.float32)

        doc_embs_list.append(doc_vec)
        docs_meta.append({
            "doc_index": doc_i,
            "section_id": (r.get("section_id") or "").strip(),
            "language": (r.get("language") or "").strip().lower(),
            "title": (r.get("title") or "").strip(),
            "num_chunks": int(len(idxs)),
            "contract_id": r.get("contract_id", ""),
            "source_file": r.get("source_file", r.get("source_path", "")),
        })

    doc_embs = np.stack(doc_embs_list, axis=0).astype(np.float32)  # [num_docs, dim]

    # save artifacts
    prefix = (args.prefix or "bge_m3").strip()

    chunks_npy = out_dir / f"{prefix}_emb_chunks.npy"
    docs_npy = out_dir / f"{prefix}_doc_embs.npy"
    chunks_meta_path = out_dir / f"{prefix}_chunks_meta.jsonl"
    docs_meta_path = out_dir / f"{prefix}_docs_meta.jsonl"

    np.save(chunks_npy, chunk_embs)
    np.save(docs_npy, doc_embs)
    write_jsonl(chunks_meta_path, chunks_meta)
    write_jsonl(docs_meta_path, docs_meta)

    # small manifest for convenience
    manifest = {
        "corpus": str(corpus_path),
        "model": str(model_path),
        "docs_selected": len(rows),
        "total_chunks": len(chunk_texts),
        "dim": dim,
        "chunk_tokens": int(args.chunk_tokens),
        "chunk_overlap": int(args.chunk_overlap),
        "files": {
            "emb_chunks_npy": str(chunks_npy),
            "chunks_meta_jsonl": str(chunks_meta_path),
            "doc_embs_npy": str(docs_npy),
            "docs_meta_jsonl": str(docs_meta_path),
        },
    }
    (out_dir / f"{prefix}_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\nDONE")
    print(f"Saved chunks embeddings: {chunks_npy}")
    print(f"Saved chunks meta:       {chunks_meta_path}")
    print(f"Saved doc embeddings:    {docs_npy}")
    print(f"Saved docs meta:         {docs_meta_path}")
    print(f"Saved manifest:          {out_dir / f'{prefix}_manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
