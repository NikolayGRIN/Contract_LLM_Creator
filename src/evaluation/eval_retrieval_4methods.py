from __future__ import annotations

import argparse
import contextlib
import csv
import datetime as dt
import json
import math
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import numpy as np


# ----------------------------
# stderr suppress (llama.cpp is noisy)
# ----------------------------
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


def write_csv(path: Path, rows: List[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


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
# Dense cosine + helpers
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


def topk_indices(scores: List[float], k: int) -> List[int]:
    k = max(1, int(k))
    return sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]


def ranks_from_scores(scores: List[float]) -> List[int]:
    order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    ranks = [0] * len(scores)
    for r, idx in enumerate(order, start=1):
        ranks[idx] = r
    return ranks


def rrf_fusion(scores_a: List[float], scores_b: List[float], k0: int = 60) -> List[float]:
    ra = ranks_from_scores(scores_a)
    rb = ranks_from_scores(scores_b)
    return [1.0 / (k0 + ra[i]) + 1.0 / (k0 + rb[i]) for i in range(len(ra))]


# ----------------------------
# Metrics @K (per-query)
# ----------------------------
def precision_recall_f1_mrr_at_k(
    retrieved_ids: List[int],
    rel_mask: List[bool],
    k: int,
) -> Tuple[float, float, float, float, int, int]:
    """
    retrieved_ids: ранжированный список индексов кандидатов (уже top-K или длиннее)
    rel_mask: True/False для каждого кандидата (релевантен ли он данному запросу)
    k: считаем метрики на первых K позициях
    Возвращаем: P@K, R@K, F1@K, MRR@K, hits@K, rel_total
    """
    k = max(1, int(k))
    topk = retrieved_ids[:k]

    hits = sum(1 for idx in topk if rel_mask[idx])
    rel_total = sum(1 for x in rel_mask if x)

    precision = hits / k

    recall = (hits / rel_total) if rel_total > 0 else 0.0

    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    mrr = 0.0
    for rank, idx in enumerate(topk, start=1):
        if rel_mask[idx]:
            mrr = 1.0 / rank
            break

    return precision, recall, f1, mrr, hits, rel_total


# ----------------------------
# Query builder (NO gold text leakage)
# ----------------------------
SECTION_KEYWORDS = {
    "payment_terms": (
        # English
        "payment terms invoice bank transfer currency prepayment advance "
        "VAT withholding set-off payment date due interest penalty late payment "
        # Russian
        " оплаты оплата счет инвойс банковский перевод валюта предоплата аванс "
        "удержание зачет платежа платеж процент просрочка"
    ),

    "delivery_terms": (
        # English
        "delivery terms shipment dispatch delivery place partial shipments schedule "
        "risk transfer title handover packaging marking carrier incoterms "
        # Russian
        "поставки отгрузка отправка место поставка частичная график "
        "переход риска право собственности передача упаковка маркировка перевозчик инкотермс"
    ),
}



def build_query(title: str, section_id: str, language: str) -> str:
    title = normalize_text(title or "")
    kw = SECTION_KEYWORDS.get(section_id, "")
    q = f"{title} {kw}".strip()
    lang = (language or "").lower()
    if lang.startswith("ru"):
        q += " russian"
    elif lang.startswith("en"):
        q += " english"
    return q.strip()


# ----------------------------
# llama.cpp wrappers
# ----------------------------
class LlamaCppEmbedder:
    def __init__(
        self,
        model_path: Path,
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


class LlamaCppReranker:
    """
    LLM-rerank: даём модели (query + candidate) и просим поставить оценку релевантности 0..3.
    Потом используем это как score для ранжирования.
    """
    def __init__(
        self,
        model_path: Path,
        *,
        n_ctx: int = 4096,
        n_threads: int = 8,
        n_gpu_layers: int = 0,
        temperature: float = 0.0,
        top_p: float = 1.0,
        top_k: int = 0,
        max_tokens: int = 16,
        verbose: bool = False,
    ):
        from llama_cpp import Llama  # type: ignore

        self.llm = Llama(
            model_path=str(model_path),
            n_ctx=int(n_ctx),
            n_threads=int(n_threads),
            n_gpu_layers=int(n_gpu_layers),
            verbose=bool(verbose),
        )
        self.temperature = float(temperature)
        self.top_p = float(top_p)
        self.top_k = int(top_k)
        self.max_tokens = int(max_tokens)

    @staticmethod
    def _prompt(query: str, candidate: str) -> str:
        # Жёсткий формат ответа нужен для надёжного парсинга.
        return (
            "You are a strict relevance judge for retrieval in a legal RAG pipeline.\n"
            "Rate how relevant the CANDIDATE is for answering the QUERY.\n"
            "Scale:\n"
            "0 = not relevant\n"
            "1 = weakly relevant\n"
            "2 = relevant\n"
            "3 = highly relevant\n"
            "Return ONLY one digit: 0,1,2,or 3.\n\n"
            f"QUERY:\n{query}\n\n"
            f"CANDIDATE:\n{candidate}\n\n"
            "DIGIT:"
        )

    @staticmethod
    def _parse_digit(text: str) -> float:
        # Ищем первую цифру 0..3.
        m = re.search(r"\b([0-3])\b", text.strip())
        if not m:
            return 0.0
        return float(m.group(1))

    def score_one(self, query: str, candidate: str) -> float:
        prompt = self._prompt(query, candidate)
        with suppress_stderr():
            resp = self.llm(
                prompt,
                temperature=self.temperature,
                top_p=self.top_p,
                top_k=self.top_k,
                max_tokens=self.max_tokens,
                stop=["\n"],
            )
        txt = resp["choices"][0]["text"]
        return self._parse_digit(txt)


# ----------------------------
# Evaluation pipeline
# ----------------------------
def main() -> int:
    ap = argparse.ArgumentParser()

    # inputs
    ap.add_argument("--corpus", type=str, default="data/corpus_sections.jsonl")
    ap.add_argument("--gold", type=str, default="data/marked_sections_labeled.jsonl")
    ap.add_argument("--sections", type=str, default="payment_terms,delivery_terms")
    ap.add_argument("--k", type=int, default=10)

    # bm25
    ap.add_argument("--bm25_k1", type=float, default=1.5)
    ap.add_argument("--bm25_b", type=float, default=0.75)

    # embeddings
    ap.add_argument("--embed_model", type=str, default="", help="GGUF embedding model path (e.g., bge-m3 gguf)")
    ap.add_argument("--embed_threads", type=int, default=8)
    ap.add_argument("--embed_gpu_layers", type=int, default=0)
    ap.add_argument("--embed_ctx", type=int, default=4096)
    ap.add_argument("--embed_batch", type=int, default=32)

    # caching embeddings
    ap.add_argument("--emb_cache_dir", type=str, default="debug/emb_cache")
    ap.add_argument("--emb_cache_npy", type=str, default="doc_embs.npy")

    # hybrid
    ap.add_argument("--rrf_k0", type=int, default=60)

    # llm rerank (optional)
    ap.add_argument("--llm_rerank", action="store_true")
    ap.add_argument("--llm_model", type=str, default="", help="GGUF instruct model path for rerank (e.g., Qwen2.5)")
    ap.add_argument("--llm_threads", type=int, default=8)
    ap.add_argument("--llm_gpu_layers", type=int, default=0)
    ap.add_argument("--llm_ctx", type=int, default=4096)
    ap.add_argument("--llm_rerank_topn", type=int, default=30, help="rerank only top-N from HYBRID")

    # outputs
    ap.add_argument("--out_dir", type=str, default="debug")

    args = ap.parse_args()

    corpus_path = Path(args.corpus)
    gold_path = Path(args.gold)
    if not corpus_path.exists():
        print(f"ERROR: corpus not found: {corpus_path}")
        return 2
    if not gold_path.exists():
        print(f"ERROR: gold not found: {gold_path}")
        return 2

    target_sections = [s.strip() for s in (args.sections or "").split(",") if s.strip()]
    if not target_sections:
        print("ERROR: empty --sections")
        return 2

    # ---- load data
    corpus = read_jsonl(corpus_path)
    gold = read_jsonl(gold_path)

    # candidates: все секции корпуса, которые размечены section_id (как у тебя)
    candidates = [r for r in corpus if (r.get("section_id") or "").strip()]
    if not candidates:
        print("ERROR: no candidates with section_id in corpus")
        return 2

    cand_texts = [f"{r.get('title','')} {r.get('text','')}".strip() for r in candidates]
    cand_section_ids = [(r.get("section_id") or "").strip() for r in candidates]
    cand_langs = [(r.get("language") or "").strip().lower() for r in candidates]

    # ---- build queries from gold only for payment_terms & delivery_terms
    # релевантность: те кандидаты, у которых section_id совпадает (и язык совпадает, если в gold есть язык)
    queries: List[Tuple[str, str, str, List[bool], str]] = []
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

        # query_id — чтобы удобно отлаживать; если doc_id есть в gold, используем его
        doc_id = str(r.get("doc_id") or r.get("source_doc_id") or "unknown_doc")
        query_id = f"{doc_id}::{sid}::{lang or 'na'}"
        queries.append((sid, lang, q, rel_mask, query_id))

    if not queries:
        print("ERROR: no queries built from gold for selected sections")
        return 2

    K = max(1, int(args.k))

    # ---- BM25 index
    bm25 = BM25.build(cand_texts, k1=float(args.bm25_k1), b=float(args.bm25_b))

    # ---- embeddings index (required for embeddings/hybrid/llm rerank)
    if not args.embed_model:
        print("ERROR: --embed_model is required (embeddings нужны для embeddings/hybrid/llm rerank)")
        return 2

    embed_model_path = Path(args.embed_model)
    if not embed_model_path.exists():
        print(f"ERROR: embed model not found: {embed_model_path}")
        return 2

    embedder = LlamaCppEmbedder(
        model_path=embed_model_path,
        n_ctx=int(args.embed_ctx),
        n_threads=int(args.embed_threads),
        n_gpu_layers=int(args.embed_gpu_layers),
    )

    cache_dir = Path(args.emb_cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / args.emb_cache_npy

    doc_embs: List[List[float]]
    if cache_path.exists():
        print(f"DEBUG: loading cached doc embeddings → {cache_path}")
        doc_embs = np.load(cache_path).astype("float32").tolist()
        if len(doc_embs) != len(cand_texts):
            print(f"DEBUG: cache mismatch ({len(doc_embs)} vs {len(cand_texts)}) → rebuild")
            doc_embs = embedder.embed_many(cand_texts, batch_size=int(args.embed_batch))
            np.save(cache_path, np.asarray(doc_embs, dtype="float32"))
    else:
        print(f"DEBUG: building doc embeddings... docs={len(cand_texts)}")
        doc_embs = embedder.embed_many(cand_texts, batch_size=int(args.embed_batch))
        np.save(cache_path, np.asarray(doc_embs, dtype="float32"))

    print(f"DEBUG: embeddings ready. docs={len(doc_embs)} dim={len(doc_embs[0]) if doc_embs else 0}")

    # ---- optional LLM reranker
    reranker: Optional[LlamaCppReranker] = None
    if args.llm_rerank:
        if not args.llm_model:
            print("ERROR: --llm_rerank requires --llm_model")
            return 2
        llm_model_path = Path(args.llm_model)
        if not llm_model_path.exists():
            print(f"ERROR: llm model not found: {llm_model_path}")
            return 2

        reranker = LlamaCppReranker(
            model_path=llm_model_path,
            n_ctx=int(args.llm_ctx),
            n_threads=int(args.llm_threads),
            n_gpu_layers=int(args.llm_gpu_layers),
            temperature=0.0,     # детерминированнее
            top_p=1.0,
            top_k=0,
            max_tokens=8,
        )

    # ---- accumulators (micro averaging over queries)
    methods = ["bm25", "embeddings", "hybrid_rrf", "llm_rerank"] if args.llm_rerank else ["bm25", "embeddings", "hybrid_rrf"]
    sums: Dict[str, Dict[str, float]] = {m: {"precision": 0.0, "recall": 0.0, "f1": 0.0, "mrr": 0.0} for m in methods}

    # ---- per-query rows for debug / analysis
    per_query_rows: List[dict] = []

    # ---- evaluation loop
    for sid, lang, q, rel_mask, query_id in queries:
        # BM25
        bm_scores = bm25.score(q)
        bm_rank = topk_indices(bm_scores, len(bm_scores))  # полный ранжированный список индексов
        bm_p, bm_r, bm_f1, bm_mrr, _, rel_total = precision_recall_f1_mrr_at_k(bm_rank, rel_mask, K)

        # Embeddings cosine
        q_emb = embedder.embed_one(q)
        emb_scores = [cosine_dense(q_emb, doc_embs[i]) for i in range(len(doc_embs))]
        emb_rank = topk_indices(emb_scores, len(emb_scores))
        e_p, e_r, e_f1, e_mrr, _, _ = precision_recall_f1_mrr_at_k(emb_rank, rel_mask, K)

        # Hybrid RRF
        rrf_scores = rrf_fusion(bm_scores, emb_scores, k0=int(args.rrf_k0))
        hy_rank = topk_indices(rrf_scores, len(rrf_scores))
        h_p, h_r, h_f1, h_mrr, _, _ = precision_recall_f1_mrr_at_k(hy_rank, rel_mask, K)

        # LLM rerank (только top-N из hybrid)
        if reranker is not None:
            topn = max(K, int(args.llm_rerank_topn))
            hy_topn = hy_rank[:topn]

            llm_scores: List[float] = []
            for idx in hy_topn:
                # чтобы LLM не “тонул” в огромном тексте, ограничим кандидата
                cand = cand_texts[idx]
                cand_short = cand[:2500]  # ~ограничение по символам, чтобы не раздувать контекст
                llm_scores.append(reranker.score_one(q, cand_short))

            # ранжируем только эти top-N; остальные считаем заведомо ниже
            # строим итоговый rank как: (переранжированный top-N) + (остальные в исходном порядке)
            order_topn = sorted(range(len(hy_topn)), key=lambda j: llm_scores[j], reverse=True)
            llm_rank = [hy_topn[j] for j in order_topn] + [idx for idx in hy_rank if idx not in set(hy_topn)]

            l_p, l_r, l_f1, l_mrr, _, _ = precision_recall_f1_mrr_at_k(llm_rank, rel_mask, K)
        else:
            l_p = l_r = l_f1 = l_mrr = 0.0

        # accumulate
        sums["bm25"]["precision"] += bm_p
        sums["bm25"]["recall"] += bm_r
        sums["bm25"]["f1"] += bm_f1
        sums["bm25"]["mrr"] += bm_mrr

        sums["embeddings"]["precision"] += e_p
        sums["embeddings"]["recall"] += e_r
        sums["embeddings"]["f1"] += e_f1
        sums["embeddings"]["mrr"] += e_mrr

        sums["hybrid_rrf"]["precision"] += h_p
        sums["hybrid_rrf"]["recall"] += h_r
        sums["hybrid_rrf"]["f1"] += h_f1
        sums["hybrid_rrf"]["mrr"] += h_mrr

        if reranker is not None:
            sums["llm_rerank"]["precision"] += l_p
            sums["llm_rerank"]["recall"] += l_r
            sums["llm_rerank"]["f1"] += l_f1
            sums["llm_rerank"]["mrr"] += l_mrr

        # per-query debug row
        row = {
            "query_id": query_id,
            "section_id": sid,
            "language": lang,
            "K": K,
            "rel_total": rel_total,
            "bm25_precision@k": bm_p,
            "bm25_recall@k": bm_r,
            "bm25_f1@k": bm_f1,
            "bm25_mrr@k": bm_mrr,
            "emb_precision@k": e_p,
            "emb_recall@k": e_r,
            "emb_f1@k": e_f1,
            "emb_mrr@k": e_mrr,
            "hybrid_precision@k": h_p,
            "hybrid_recall@k": h_r,
            "hybrid_f1@k": h_f1,
            "hybrid_mrr@k": h_mrr,
        }
        if reranker is not None:
            row.update(
                {
                    "llm_precision@k": l_p,
                    "llm_recall@k": l_r,
                    "llm_f1@k": l_f1,
                    "llm_mrr@k": l_mrr,
                }
            )
        per_query_rows.append(row)

    # ---- macro average over queries
    n = len(queries)
    summary_rows: List[dict] = []
    for m in methods:
        summary_rows.append(
            {
                "method": m,
                "K": K,
                "queries": n,
                "precision@k": sums[m]["precision"] / n,
                "recall@k": sums[m]["recall"] / n,
                "f1@k": sums[m]["f1"] / n,
                "mrr@k": sums[m]["mrr"] / n,
            }
        )

    # ---- print summary
    print(f"Queries: {n} | Candidates: {len(candidates)} | Sections: {target_sections} | K={K}")
    print(f"Embeddings cache: {cache_path}")
    if reranker is not None:
        print(f"LLM rerank: ON | topN={int(args.llm_rerank_topn)} | model={args.llm_model}")
    else:
        print("LLM rerank: OFF")

    print("\n=== METRICS (macro over queries) ===")
    for r in summary_rows:
        print(
            f"[{r['method']}] "
            f"P@{K}={r['precision@k']:.4f} "
            f"R@{K}={r['recall@k']:.4f} "
            f"F1@{K}={r['f1@k']:.4f} "
            f"MRR@{K}={r['mrr@k']:.4f}"
        )

    # ---- save artifacts
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")

    out_summary_csv = out_dir / f"retrieval_metrics_summary_{stamp}.csv"
    out_perquery_csv = out_dir / f"retrieval_metrics_per_query_{stamp}.csv"
    out_json = out_dir / f"retrieval_metrics_{stamp}.json"

    write_csv(out_summary_csv, summary_rows)
    write_csv(out_perquery_csv, per_query_rows)

    meta = {
        "timestamp": stamp,
        "corpus": str(corpus_path),
        "gold": str(gold_path),
        "sections": target_sections,
        "K": K,
        "bm25_k1": float(args.bm25_k1),
        "bm25_b": float(args.bm25_b),
        "embed_model": str(embed_model_path),
        "embed_cache": str(cache_path),
        "rrf_k0": int(args.rrf_k0),
        "llm_rerank": bool(args.llm_rerank),
        "llm_model": args.llm_model if args.llm_rerank else None,
        "llm_rerank_topn": int(args.llm_rerank_topn),
    }

    out_json.write_text(
        json.dumps({"meta": meta, "summary": summary_rows, "per_query": per_query_rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\nSaved: {out_summary_csv}")
    print(f"Saved: {out_perquery_csv}")
    print(f"Saved: {out_json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
