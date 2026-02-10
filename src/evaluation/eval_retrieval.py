# src/evaluation/eval_retrieval.py
from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import contextlib
import os
import sys
import datetime
import csv

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
    out = []
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
    s = normalize_text(s)
    return _WORD_RE.findall(s)


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
            seen = set(toks)
            for w in seen:
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
# Embeddings (cosine): TF-IDF fallback (no extra deps)
# ----------------------------
def build_tfidf_matrix(texts: List[str]) -> Tuple[List[Dict[str, float]], Dict[str, float]]:
    tokenized = [tokenize(t) for t in texts]
    N = len(tokenized)
    df: Dict[str, int] = {}
    for toks in tokenized:
        for w in set(toks):
            df[w] = df.get(w, 0) + 1

    idf: Dict[str, float] = {}
    for w, dfi in df.items():
        idf[w] = math.log((N + 1) / (dfi + 1)) + 1.0

    vectors: List[Dict[str, float]] = []
    for toks in tokenized:
        tf: Dict[str, int] = {}
        for w in toks:
            tf[w] = tf.get(w, 0) + 1
        v: Dict[str, float] = {}
        for w, c in tf.items():
            v[w] = (c / (len(toks) or 1)) * idf.get(w, 0.0)
        vectors.append(v)

    return vectors, idf

def tfidf_vector(query: str, idf: Dict[str, float]) -> Dict[str, float]:
    toks = tokenize(query)
    tf: Dict[str, int] = {}
    for w in toks:
        tf[w] = tf.get(w, 0) + 1
    v: Dict[str, float] = {}
    for w, c in tf.items():
        v[w] = (c / (len(toks) or 1)) * idf.get(w, 0.0)
    return v

def cosine_sparse(a: Dict[str, float], b: Dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    dot = 0.0
    if len(a) > len(b):
        a, b = b, a
    for k, va in a.items():
        vb = b.get(k)
        if vb is not None:
            dot += va * vb
    na = math.sqrt(sum(x * x for x in a.values()))
    nb = math.sqrt(sum(x * x for x in b.values()))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


# ----------------------------
# llama.cpp embeddings (dense cosine)
# ----------------------------
def cosine_dense(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    # assume same dim
    for i in range(min(len(a), len(b))):
        va = float(a[i]); vb = float(b[i])
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
        n_ctx: int = 2048,
        n_threads: int = 8,
        n_gpu_layers: int = 0,
        verbose: bool = False,
    ):
        from llama_cpp import Llama  # type: ignore

        self.model = Llama(
            model_path=str(model_path),  # ВАЖНО: str, не Path
            embedding=True,
            n_ctx=int(n_ctx),
            n_threads=int(n_threads),
            n_gpu_layers=int(n_gpu_layers),
            verbose=bool(verbose),
        )

    def embed_one(self, text: str) -> list[float]:
        with suppress_stderr():
            resp = self.model.create_embedding(text or "")
        return resp["data"][0]["embedding"]

    def embed_many(self, texts: list[str], *, batch_size: int = 16) -> list[list[float]]:
        out: list[list[float]] = []
        bs = max(1, int(batch_size))

        # ВАЖНО: у llama.cpp нет "настоящего батча" как в torch,
        # поэтому просто группируем вызовы, чтобы контролировать прогресс/память.
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
# Scoring + metrics
# ----------------------------
def topk_indices(scores: List[float], k: int) -> List[int]:
    k = max(1, k)
    return sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]

def minmax_norm(scores: List[float]) -> List[float]:
    if not scores:
        return scores
    mn = min(scores)
    mx = max(scores)
    if mx - mn < 1e-12:
        return [0.0 for _ in scores]
    return [(s - mn) / (mx - mn) for s in scores]

def recall_at_k(retrieved: List[int], rel_mask: List[bool]) -> float:
    for idx in retrieved:
        if rel_mask[idx]:
            return 1.0
    return 0.0

def precision_at_k(retrieved: List[int], rel_mask: List[bool]) -> float:
    """
    precision@k = (# релевантных среди retrieved) / k

    В отличие от recall@k, показывает долю "шума" в выдаче.
    Для RAG менее критичен, но полезен для анализа качества ранжирования.
    """
    if not retrieved:
        return 0.0
    hits = sum(1 for idx in retrieved if rel_mask[idx])
    return hits / len(retrieved)


def mrr_at_k(retrieved: List[int], rel_mask: List[bool]) -> float:
    for rank, idx in enumerate(retrieved, start=1):
        if rel_mask[idx]:
            return 1.0 / rank
    return 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=str, default="data/corpus_sections.jsonl")
    ap.add_argument("--gold", type=str, default="data/marked_sections_labeled.jsonl")
    ap.add_argument("--sections", type=str, default="payment_terms,delivery_terms",
                    help="comma-separated section_id to evaluate as queries")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--bm25_k1", type=float, default=1.5)
    ap.add_argument("--bm25_b", type=float, default=0.75)
    ap.add_argument("--hybrid_alpha", type=float, default=0.5,
                    help="0..1: alpha*BM25 + (1-alpha)*cosine")

    # ✅ llama.cpp embeddings options
    ap.add_argument("--llama_embed", action="store_true", help="enable llama.cpp embeddings (dense cosine)")
    ap.add_argument("--llama_embed_model", type=str, default="", help="path to embedding-capable GGUF model")
    ap.add_argument("--llama_embed_batch", type=int, default=32)
    ap.add_argument("--llama_embed_threads", type=int, default=8)
    ap.add_argument("--llama_embed_gpu_layers", type=int, default=0)
    ap.add_argument("--llama_embed_ctx", type=int, default=4096)

    ap.add_argument("--llama_doc_index_npy", type=str, default="",
                help="path to precomputed doc embeddings .npy (skip building)")
    ap.add_argument("--llama_docs_meta", type=str, default="",
                help="path to docs_meta.jsonl matching the .npy order")

    args = ap.parse_args()

    corpus_path = Path(args.corpus)
    gold_path = Path(args.gold)

    corpus = read_jsonl(corpus_path)
    gold = read_jsonl(gold_path)

    target_sections = [s.strip() for s in args.sections.split(",") if s.strip()]
    if not target_sections:
        print("ERROR: empty --sections")
        return 2

    candidates = [r for r in corpus if (r.get("section_id") or "").strip()]
    if not candidates:
        print("ERROR: no candidates with section_id in corpus")
        return 2

    cand_texts = [f"{r.get('title','')} {r.get('text','')}" for r in candidates]
    cand_section_ids = [(r.get("section_id") or "").strip() for r in candidates]
    cand_langs = [(r.get("language") or "").strip().lower() for r in candidates]

    # ----------------------------
    # Indexes (BUILD ONCE)
    # ----------------------------
    bm25 = BM25.build(cand_texts, k1=args.bm25_k1, b=args.bm25_b)
    tfidf_vecs, tfidf_idf = build_tfidf_matrix(cand_texts)

    # ✅ llama embeddings index (optional, BUILD ONCE)
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

        print(f"DEBUG: building llama embeddings index... docs={len(cand_texts)}")
        embedder = LlamaCppEmbedder(
            model_path=model_path,
            n_ctx=int(args.llama_embed_ctx),
            n_threads=int(args.llama_embed_threads),
            n_gpu_layers=int(args.llama_embed_gpu_layers),
        )
        doc_embs = embedder.embed_many(cand_texts, batch_size=int(args.llama_embed_batch))
        print(f"DEBUG: llama embeddings ready. dim={len(doc_embs[0]) if doc_embs else 0}")

    # ----------------------------
    # Build query set from gold
    # ----------------------------
    queries = []
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

    K = args.k
    k5 = min(5, K)
    k10 = min(10, K)

    # ----------------------------
    # Evaluate methods
    # ----------------------------
    stats = {
        "bm25": {"recall@5": 0.0, "recall@10": 0.0, "precision@10": 0.0, "mrr@10": 0.0},
        "emb_tfidf": {"recall@5": 0.0, "recall@10": 0.0, "precision@10": 0.0, "mrr@10": 0.0},
        "hybrid": {"recall@5": 0.0, "recall@10": 0.0, "precision@10": 0.0, "mrr@10": 0.0},
        "emb_llama": {"recall@5": 0.0, "recall@10": 0.0, "precision@10": 0.0, "mrr@10": 0.0},
        "hybrid_llama": {"recall@5": 0.0, "recall@10": 0.0, "precision@10": 0.0, "mrr@10": 0.0},
    }
    
    for sid, lang, q, rel_mask in queries:
        # --- BM25
        bm_scores = bm25.score(q)
        bm_top5 = topk_indices(bm_scores, k5)
        bm_top10 = topk_indices(bm_scores, k10)

        stats["bm25"]["recall@5"] += recall_at_k(bm_top5, rel_mask)
        stats["bm25"]["recall@10"] += recall_at_k(bm_top10, rel_mask)
        stats["bm25"]["mrr@10"] += mrr_at_k(bm_top10, rel_mask)
        stats["bm25"]["precision@10"] += precision_at_k(bm_top10, rel_mask)

        # --- TF-IDF cosine baseline
        qv = tfidf_vector(q, tfidf_idf)
        cos_scores = [cosine_sparse(qv, tfidf_vecs[i]) for i in range(len(tfidf_vecs))]
        cos_top5 = topk_indices(cos_scores, k5)
        cos_top10 = topk_indices(cos_scores, k10)

        stats["emb_tfidf"]["recall@5"] += recall_at_k(cos_top5, rel_mask)
        stats["emb_tfidf"]["recall@10"] += recall_at_k(cos_top10, rel_mask)
        stats["emb_tfidf"]["mrr@10"] += mrr_at_k(cos_top10, rel_mask)
        stats["emb_tfidf"]["precision@10"] += precision_at_k(cos_top10, rel_mask)

        # --- Hybrid: BM25 + TFIDF-cosine
        bm_n = minmax_norm(bm_scores)
        cos_n = minmax_norm(cos_scores)
        a = float(args.hybrid_alpha)
        hy_scores = [a * bm_n[i] + (1.0 - a) * cos_n[i] for i in range(len(bm_n))]
        hy_top5 = topk_indices(hy_scores, k5)
        hy_top10 = topk_indices(hy_scores, k10)

        stats["hybrid"]["recall@5"] += recall_at_k(hy_top5, rel_mask)
        stats["hybrid"]["recall@10"] += recall_at_k(hy_top10, rel_mask)
        stats["hybrid"]["mrr@10"] += mrr_at_k(hy_top10, rel_mask)
        stats["hybrid"]["precision@10"] += precision_at_k(hy_top10, rel_mask)

        # --- llama embeddings (optional)
        if args.llama_embed and embedder is not None and doc_embs is not None:
            q_emb = embedder.embed_one(q)
            llama_scores = [cosine_dense(q_emb, doc_embs[i]) for i in range(len(doc_embs))]
            llama_top5 = topk_indices(llama_scores, k5)
            llama_top10 = topk_indices(llama_scores, k10)

            stats["emb_llama"]["recall@5"] += recall_at_k(llama_top5, rel_mask)
            stats["emb_llama"]["recall@10"] += recall_at_k(llama_top10, rel_mask)
            stats["emb_llama"]["mrr@10"] += mrr_at_k(llama_top10, rel_mask)
            stats["emb_llama"]["precision@10"] += precision_at_k(llama_top10, rel_mask)

            # hybrid with llama cosine
            llama_n = minmax_norm(llama_scores)
            hy_llama_scores = [a * bm_n[i] + (1.0 - a) * llama_n[i] for i in range(len(bm_n))]
            hy_llama_top5 = topk_indices(hy_llama_scores, k5)
            hy_llama_top10 = topk_indices(hy_llama_scores, k10)

            stats["hybrid_llama"]["recall@5"] += recall_at_k(hy_llama_top5, rel_mask)
            stats["hybrid_llama"]["recall@10"] += recall_at_k(hy_llama_top10, rel_mask)
            stats["hybrid_llama"]["mrr@10"] += mrr_at_k(hy_llama_top10, rel_mask)
            stats["hybrid_llama"]["precision@10"] += precision_at_k(hy_llama_top10, rel_mask)

    n = len(queries)
    for m in stats:
        for kk in stats[m]:
            stats[m][kk] = stats[m][kk] / n

    print(f"Queries used: {n} | Candidates: {len(candidates)} | Sections: {target_sections}")
    print(f"Hybrid alpha: {args.hybrid_alpha} | K={K}")
    if args.llama_embed:
        print(f"Llama embeddings: enabled | model={args.llama_embed_model} | batch={args.llama_embed_batch}")
    print()

    for m, d in stats.items():
        print(
            f"[{m}] "
            f"recall@5={d['recall@5']:.3f} "
            f"recall@10={d['recall@10']:.3f} "
            f"precision@10={d['precision@10']:.3f} "
            f"mrr@10={d['mrr@10']:.3f}"
        )

    # -----------------------------
    # SAVE METRICS (LONG/TIDY FORMAT)
    # -----------------------------
    out_dir = Path(getattr(args, "out_dir", "debug"))  # если args.out_dir нет -> debug/
    out_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # зафиксируй порядок методов (как на твоём слайде)
    method_order = [
        "bm25",
        "emb_tfidf",      # TF-IDF cosine baseline
        "hybrid",
        "emb_llama",      # llama embeddings
        "hybrid_llama",   # hybrid + llama
    ]
    # на случай если каких-то ключей нет
    method_order = [m for m in method_order if m in stats] + [m for m in stats.keys() if m not in method_order]

    metric_order = ["recall@5", "recall@10", "precision@10", "mrr@10"]

    rows_long = []
    for m in method_order:
        d = stats[m]
        for metric in metric_order:
            rows_long.append(
                {
                    "method": m,
                    "metric": metric,
                    "value": float(d[metric]),
                    "K": int(K),
                    "hybrid_alpha": float(args.hybrid_alpha),
                    "queries_used": int(n),
                    "candidates": int(len(candidates)),
                }
            )

    meta = {
        "timestamp": stamp,
        "queries_used": n,
        "candidates": len(candidates),
        "sections": target_sections,
        "K": K,
        "hybrid_alpha": float(args.hybrid_alpha),
        "llama_embed": bool(getattr(args, "llama_embed", False)),
        "llama_embed_model": getattr(args, "llama_embed_model", None),
        "llama_embed_batch": int(getattr(args, "llama_embed_batch", 0) or 0),
        "method_order": method_order,
        "metric_order": metric_order,
    }

    # JSON (long)
    out_json = out_dir / f"retrieval_metrics_long_{stamp}.json"
    out_json.write_text(
        json.dumps({"meta": meta, "rows": rows_long}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nSaved metrics JSON (long) to: {out_json}")

    # CSV (long)
    out_csv = out_dir / f"retrieval_metrics_long_{stamp}.csv"
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_long[0].keys()))
        w.writeheader()
        w.writerows(rows_long)
    print(f"Saved metrics CSV (long) to: {out_csv}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
