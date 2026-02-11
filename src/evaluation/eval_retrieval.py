# src/evaluation/eval_retrieval.py
from __future__ import annotations

import argparse
import contextlib
import csv
import datetime
import json
import math
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np


@contextlib.contextmanager
def suppress_stderr():
    old = sys.stderr
    try:
        with open(os.devnull, "w") as devnull:
            sys.stderr = devnull
            yield
    finally:
        sys.stderr = old


# ----------------------------
# IO helpers
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


# ----------------------------
# Text normalization/tokenization
# ----------------------------
_WORD_RE = re.compile(r"[A-Za-zА-Яа-я0-9]+", re.UNICODE)


def normalize_text(s: str) -> str:
    s = (s or "").lower()
    s = s.replace("\u00a0", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def tokenize(s: str) -> List[str]:
    return _WORD_RE.findall(normalize_text(s))


# ----------------------------
# BM25 (minimal Okapi)
# ----------------------------
@dataclass
class BM25:
    docs_tokens: List[List[str]]
    idf: Dict[str, float]
    avgdl: float
    k1: float = 1.5
    b: float = 0.75

    @classmethod
    def build(cls, docs_text: List[str], k1: float = 1.5, b: float = 0.75) -> "BM25":
        docs_tokens = [tokenize(t) for t in docs_text]
        N = len(docs_tokens)
        df: Dict[str, int] = {}
        dl_sum = 0

        for toks in docs_tokens:
            dl_sum += len(toks)
            for w in set(toks):
                df[w] = df.get(w, 0) + 1

        avgdl = (dl_sum / N) if N else 0.0

        idf: Dict[str, float] = {}
        for w, dfi in df.items():
            idf[w] = math.log(1 + (N - dfi + 0.5) / (dfi + 0.5))

        return cls(docs_tokens=docs_tokens, idf=idf, avgdl=avgdl, k1=k1, b=b)

    def score(self, query: str) -> List[float]:
        q = tokenize(query)
        if not q:
            return [0.0] * len(self.docs_tokens)

        scores = [0.0] * len(self.docs_tokens)
        for i, doc in enumerate(self.docs_tokens):
            if not doc:
                continue
            dl = len(doc)

            freqs: Dict[str, int] = {}
            for w in doc:
                freqs[w] = freqs.get(w, 0) + 1

            s = 0.0
            for w in q:
                if w not in freqs:
                    continue
                f = freqs[w]
                idf = self.idf.get(w, 0.0)
                denom = f + self.k1 * (1 - self.b + self.b * (dl / (self.avgdl or 1.0)))
                s += idf * (f * (self.k1 + 1)) / (denom or 1.0)

            scores[i] = s

        return scores


# ----------------------------
# llama.cpp embeddings (dense cosine)
# ----------------------------
def cosine_dense(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    n = min(len(a), len(b))
    for i in range(n):
        va = float(a[i])
        vb = float(b[i])
        dot += va * vb
        na += va * va
        nb += vb * vb
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


class LlamaCppEmbedder:
    def __init__(
        self,
        model_path,
        *,
        n_ctx: int = 4096,
        n_threads: int = 8,
        n_gpu_layers: int = 0,
        verbose: bool = False,
    ):
        from llama_cpp import Llama  # type: ignore

        self.model = Llama(
            model_path=str(model_path),
            embedding=True,
            n_ctx=int(n_ctx),
            n_threads=int(n_threads),
            n_gpu_layers=int(n_gpu_layers),
            verbose=bool(verbose),
        )

    def embed_one(self, text: str) -> List[float]:
        with suppress_stderr():
            resp = self.model.create_embedding(text or "")
        return resp["data"][0]["embedding"]

    def embed_many(self, texts: List[str], *, batch_size: int = 16) -> List[List[float]]:
        out: List[List[float]] = []
        bs = max(1, int(batch_size))
        for i in range(0, len(texts), bs):
            chunk = texts[i : i + bs]
            for t in chunk:
                out.append(self.embed_one(t))
        return out


# ----------------------------
# Query builder (NO gold text)
# ----------------------------
SECTION_KEYWORDS = {
    "payment_terms": "payment terms invoice bank transfer currency prepayment advance VAT withholding set-off payment date due",
    "delivery_terms": "delivery terms shipment dispatch delivery place partial shipments schedule risk transfer title handover packaging marking carrier",
    "definitions": "definitions terms meanings party parties supplier buyer contract goods equipment specification annex",
    "price_and_taxes": "price contract price taxes VAT duties fees currency invoice",
    "acceptance_and_inspection": "acceptance inspection delivery note act protocol discrepancies defects notice",
    "warranties": "warranty warranty period defects repair replacement",
    "governing_law_and_disputes": "governing law jurisdiction court arbitration disputes claims",
    "force_majeure": "force majeure act of god unforeseeable unavoidable notice evidence suspension",
    "liability_and_penalties": "liability limitation cap penalties damages indirect loss",
    "subject_of_contract": "subject matter supply goods equipment products seller buyer shall purchase specification provide contract object items materials services",
}


def build_query(title: str, section_id: str, language: str) -> str:
    title = normalize_text(title or "")
    kw = SECTION_KEYWORDS.get(section_id, "")
    q = f"{title} {kw}".strip()
    if (language or "").lower().startswith("ru"):
        q += " russian"
    elif (language or "").lower().startswith("en"):
        q += " english"
    return q.strip()


# ----------------------------
# Ranking + fusion helpers
# ----------------------------
def topk_indices(scores: List[float], k: int) -> List[int]:
    k = max(1, int(k))
    return sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]


def ranks_from_scores(scores: List[float]) -> List[int]:
    """rank=1 for best score"""
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    ranks = [0] * len(scores)
    for r, idx in enumerate(order, start=1):
        ranks[idx] = r
    return ranks


def rrf_fusion(scores_a: List[float], scores_b: List[float], k0: int = 60) -> List[float]:
    """
    Reciprocal Rank Fusion (RRF):
    score(d) = 1/(k0+rank_a(d)) + 1/(k0+rank_b(d))
    """
    ra = ranks_from_scores(scores_a)
    rb = ranks_from_scores(scores_b)
    return [1.0 / (k0 + ra[i]) + 1.0 / (k0 + rb[i]) for i in range(len(ra))]


# ----------------------------
# Metrics
# ----------------------------
def hit_at_k(retrieved: List[int], rel_mask: List[bool]) -> float:
    """Hit@K: 1 если в топ-K есть хотя бы один релевантный, иначе 0"""
    for idx in retrieved:
        if rel_mask[idx]:
            return 1.0
    return 0.0


def precision_at_k(retrieved: List[int], rel_mask: List[bool]) -> float:
    if not retrieved:
        return 0.0
    hits = sum(1 for idx in retrieved if rel_mask[idx])
    return hits / len(retrieved)


def mrr_at_k(retrieved: List[int], rel_mask: List[bool]) -> float:
    for rank, idx in enumerate(retrieved, start=1):
        if rel_mask[idx]:
            return 1.0 / rank
    return 0.0


# ----------------------------
# Plotting
# ----------------------------
def save_plot_png(stats: Dict[str, Dict[str, float]], out_path: Path, title: str) -> None:
    """
    Auto-builds a grouped bar chart into PNG.
    IMPORTANT: do not set explicit colors (per your rules).
    """
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception as e:
        print(f"WARNING: matplotlib not available, skip plot. ({e})")
        return

    methods = list(stats.keys())
    metrics = list(next(iter(stats.values())).keys())

    x = np.arange(len(methods), dtype=float)
    width = 0.8 / max(1, len(metrics))

    plt.figure(figsize=(12, 6))
    for j, metric in enumerate(metrics):
        vals = [stats[m][metric] for m in methods]
        plt.bar(x + (j - (len(metrics) - 1) / 2) * width, vals, width, label=metric)

    plt.xticks(x, methods, rotation=0)
    plt.ylim(0.0, 1.0)
    plt.ylabel("Score")
    plt.title(title)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=200)
    plt.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=str, default="data/corpus_sections.jsonl")
    ap.add_argument("--gold", type=str, default="data/marked_sections_labeled.jsonl")
    ap.add_argument(
        "--sections",
        type=str,
        default="payment_terms,delivery_terms",
        help="comma-separated section_id to evaluate as queries",
    )
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--bm25_k1", type=float, default=1.5)
    ap.add_argument("--bm25_b", type=float, default=0.75)

    # llama.cpp embeddings options
    ap.add_argument("--llama_embed", action="store_true", help="enable llama.cpp embeddings (dense cosine)")
    ap.add_argument("--llama_embed_model", type=str, default="", help="path to embedding-capable GGUF model")
    ap.add_argument("--llama_embed_batch", type=int, default=32)
    ap.add_argument("--llama_embed_threads", type=int, default=8)
    ap.add_argument("--llama_embed_gpu_layers", type=int, default=0)
    ap.add_argument("--llama_embed_ctx", type=int, default=4096)

    # Hybrid via RRF (BM25 + embeddings)
    ap.add_argument("--rrf_k0", type=int, default=60)

    # output
    ap.add_argument("--out_dir", type=str, default="debug")

    # optional: cache embeddings (doc vectors)
    ap.add_argument("--emb_cache_dir", type=str, default="debug/emb_index_bge_m3")
    ap.add_argument("--emb_cache_npy", type=str, default="bge_m3_doc_embs.npy")

    args = ap.parse_args()

    corpus_path = Path(args.corpus)
    gold_path = Path(args.gold)
    if not corpus_path.exists():
        print(f"ERROR: corpus not found: {corpus_path}")
        return 2
    if not gold_path.exists():
        print(f"ERROR: gold not found: {gold_path}")
        return 2

    corpus = read_jsonl(corpus_path)
    gold = read_jsonl(gold_path)

    target_sections = [s.strip() for s in (args.sections or "").split(",") if s.strip()]
    if not target_sections:
        print("ERROR: empty --sections")
        return 2

    candidates = [r for r in corpus if (r.get("section_id") or "").strip()]
    if not candidates:
        print("ERROR: no candidates with section_id in corpus")
        return 2

    cand_texts = [f"{r.get('title','')} {r.get('text','')}".strip() for r in candidates]
    cand_section_ids = [(r.get("section_id") or "").strip() for r in candidates]
    cand_langs = [(r.get("language") or "").strip().lower() for r in candidates]

    # Build BM25 once
    bm25 = BM25.build(cand_texts, k1=args.bm25_k1, b=args.bm25_b)

    # Build / load embeddings once (optional)
    embedder: Optional[LlamaCppEmbedder] = None
    doc_embs: Optional[List[List[float]]] = None

    if args.llama_embed:
        if not args.llama_embed_model:
            print("ERROR: --llama_embed requires --llama_embed_model")
            return 2
        model_path = Path(args.llama_embed_model)
        if not model_path.exists():
            print(f"ERROR: embedding model not found: {model_path}")
            return 2

        embedder = LlamaCppEmbedder(
            model_path=model_path,
            n_ctx=int(args.llama_embed_ctx),
            n_threads=int(args.llama_embed_threads),
            n_gpu_layers=int(args.llama_embed_gpu_layers),
        )

        cache_dir = Path(args.emb_cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = cache_dir / args.emb_cache_npy

        if cache_path.exists():
            print(f"DEBUG: loading cached embeddings → {cache_path}")
            doc_embs = np.load(cache_path).astype("float32").tolist()

            if len(doc_embs) != len(cand_texts):
                print(f"DEBUG: cache mismatch (have {len(doc_embs)} vs need {len(cand_texts)}) → rebuilding")
                doc_embs = embedder.embed_many(cand_texts, batch_size=int(args.llama_embed_batch))
                np.save(cache_path, np.asarray(doc_embs, dtype="float32"))
        else:
            print(f"DEBUG: building llama embeddings index... docs={len(cand_texts)}")
            doc_embs = embedder.embed_many(cand_texts, batch_size=int(args.llama_embed_batch))
            np.save(cache_path, np.asarray(doc_embs, dtype="float32"))

        if doc_embs:
            print(f"DEBUG: llama embeddings ready. dim={len(doc_embs[0])}")

    # Build query set from gold
    queries: List[tuple[str, str, str, List[bool]]] = []
    for r in gold:
        sid = (r.get("section_id") or "").strip()
        if sid not in target_sections:
            continue
        title = r.get("title", "")
        lang = (r.get("language") or "").strip().lower()
        q = build_query(title=title, section_id=sid, language=lang)

        if lang:
            rel_mask = [(cand_section_ids[i] == sid and cand_langs[i] == lang) for i in range(len(candidates))]
        else:
            rel_mask = [(cand_section_ids[i] == sid) for i in range(len(candidates))]

        if not any(rel_mask):
            continue
        queries.append((sid, lang, q, rel_mask))

    if not queries:
        print("ERROR: no queries from gold for selected sections (or no matching candidates)")
        return 2

    K = int(args.k)
    k5 = min(5, K)
    k10 = min(10, K)

    # Evaluate ONLY: bm25, emb_llama, hybrid_llama_rrf
    stats: Dict[str, Dict[str, float]] = {
        "bm25": {"hit@5": 0.0, "hit@10": 0.0, "precision@10": 0.0, "mrr@10": 0.0},
        "emb_bge_m3": {"hit@5": 0.0, "hit@10": 0.0, "precision@10": 0.0, "mrr@10": 0.0},
        "hybrid_rrf": {"hit@5": 0.0, "hit@10": 0.0, "precision@10": 0.0, "mrr@10": 0.0},
    }

    for _sid, _lang, q, rel_mask in queries:
        # BM25
        bm_scores = bm25.score(q)
        bm_top5 = topk_indices(bm_scores, k5)
        bm_top10 = topk_indices(bm_scores, k10)

        stats["bm25"]["hit@5"] += hit_at_k(bm_top5, rel_mask)
        stats["bm25"]["hit@10"] += hit_at_k(bm_top10, rel_mask)
        stats["bm25"]["precision@10"] += precision_at_k(bm_top10, rel_mask)
        stats["bm25"]["mrr@10"] += mrr_at_k(bm_top10, rel_mask)

        # Embeddings + Hybrid (only if enabled)
        if args.llama_embed and embedder is not None and doc_embs is not None:
            q_emb = embedder.embed_one(q)
            emb_scores = [cosine_dense(q_emb, doc_embs[i]) for i in range(len(doc_embs))]
            emb_top5 = topk_indices(emb_scores, k5)
            emb_top10 = topk_indices(emb_scores, k10)

            stats["emb_bge_m3"]["hit@5"] += hit_at_k(emb_top5, rel_mask)
            stats["emb_bge_m3"]["hit@10"] += hit_at_k(emb_top10, rel_mask)
            stats["emb_bge_m3"]["precision@10"] += precision_at_k(emb_top10, rel_mask)
            stats["emb_bge_m3"]["mrr@10"] += mrr_at_k(emb_top10, rel_mask)

            rrf_scores = rrf_fusion(bm_scores, emb_scores, k0=int(args.rrf_k0))
            rrf_top5 = topk_indices(rrf_scores, k5)
            rrf_top10 = topk_indices(rrf_scores, k10)

            stats["hybrid_rrf"]["hit@5"] += hit_at_k(rrf_top5, rel_mask)
            stats["hybrid_rrf"]["hit@10"] += hit_at_k(rrf_top10, rel_mask)
            stats["hybrid_rrf"]["precision@10"] += precision_at_k(rrf_top10, rel_mask)
            stats["hybrid_rrf"]["mrr@10"] += mrr_at_k(rrf_top10, rel_mask)

    n = len(queries)
    for m in stats:
        for metric in stats[m]:
            stats[m][metric] = stats[m][metric] / n

    print(f"Queries used: {n} | Candidates: {len(candidates)} | Sections: {target_sections}")
    print(f"K={K} | eval@5={k5} eval@10={k10} | RRF k0={args.rrf_k0}")
    if args.llama_embed:
        print(f"Llama embeddings: enabled | model={args.llama_embed_model} | batch={args.llama_embed_batch}")
    else:
        print("Llama embeddings: disabled (ONLY BM25 will be meaningful)")
    print()

    for m, d in stats.items():
        print(
            f"[{m}] "
            f"hit@5={d['hit@5']:.3f} "
            f"hit@10={d['hit@10']:.3f} "
            f"precision@10={d['precision@10']:.3f} "
            f"mrr@10={d['mrr@10']:.3f}"
        )

    # Save metrics (long format) + PNG plot
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    method_order = ["bm25", "emb_bge_m3", "hybrid_rrf"]
    metric_order = ["hit@5", "hit@10", "precision@10", "mrr@10"]

    rows_long: List[dict] = []
    for m in method_order:
        d = stats[m]
        for metric in metric_order:
            rows_long.append(
                {
                    "method": m,
                    "metric": metric,
                    "value": float(d[metric]),
                    "K": int(K),
                    "eval_k5": int(k5),
                    "eval_k10": int(k10),
                    "queries_used": int(n),
                    "candidates": int(len(candidates)),
                    "rrf_k0": int(args.rrf_k0),
                    "llama_embed_enabled": bool(args.llama_embed),
                    "llama_embed_model": args.llama_embed_model if args.llama_embed else "",
                }
            )

    meta = {
        "timestamp": stamp,
        "queries_used": n,
        "candidates": len(candidates),
        "sections": target_sections,
        "K": K,
        "eval_k5": k5,
        "eval_k10": k10,
        "rrf_k0": int(args.rrf_k0),
        "llama_embed": bool(args.llama_embed),
        "llama_embed_model": args.llama_embed_model if args.llama_embed else None,
        "llama_embed_batch": int(args.llama_embed_batch),
        "method_order": method_order,
        "metric_order": metric_order,
        "emb_cache_dir": str(Path(args.emb_cache_dir)),
        "emb_cache_npy": str(Path(args.emb_cache_dir) / args.emb_cache_npy),
    }

    out_json = out_dir / f"retrieval_metrics_long_{stamp}.json"
    out_json.write_text(json.dumps({"meta": meta, "rows": rows_long}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved metrics JSON (long) to: {out_json}")

    out_csv = out_dir / f"retrieval_metrics_long_{stamp}.csv"
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_long[0].keys()))
        w.writeheader()
        w.writerows(rows_long)
    print(f"Saved metrics CSV (long) to: {out_csv}")

    out_png = out_dir / f"retrieval_metrics_plot_{stamp}.png"
    save_plot_png(
        stats=stats,
        out_path=out_png,
        title=f"Сравнение метрик Retrieval (K={k10})",
    )
    if out_png.exists():
        print(f"Saved plot PNG to: {out_png}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
