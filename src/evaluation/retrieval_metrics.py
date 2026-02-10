# src/evaluation/retrieval_metrics.py
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Iterable, Optional

CORPUS = Path(r"data/corpus_sections.jsonl")
GOLD = Path(r"data/marked_sections.jsonl")

EVAL_SECTION_IDS = {"payment_terms", "delivery_terms"}  # можешь расширить
TOP_KS = [1, 3, 5, 10]

def tokenize(s: str) -> List[str]:
    s = (s or "").lower()
    s = re.sub(r"[^a-zа-яё0-9]+", " ", s, flags=re.IGNORECASE)
    toks = [t for t in s.split() if len(t) >= 2]
    return toks

def build_query_from_gold(text: str, *, max_words: int = 35) -> str:
    # псевдо-запрос: первые N слов (без цифр/мусора)
    words = re.findall(r"[A-Za-zА-Яа-яЁё0-9]+", text)
    words = [w for w in words if not re.fullmatch(r"\d+", w)]
    return " ".join(words[:max_words])

@dataclass
class Doc:
    doc_id: str
    section_id: str
    language: str
    text: str

class BM25Index:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.docs: List[Doc] = []
        self.tf: List[Dict[str, int]] = []
        self.df: Dict[str, int] = {}
        self.avgdl: float = 0.0

    def add(self, docs: List[Doc]) -> None:
        self.docs = docs
        self.tf = []
        self.df = {}
        total_len = 0

        for d in docs:
            toks = tokenize(d.text)
            total_len += len(toks)
            counts: Dict[str, int] = {}
            for t in toks:
                counts[t] = counts.get(t, 0) + 1
            self.tf.append(counts)
            for t in counts.keys():
                self.df[t] = self.df.get(t, 0) + 1

        self.avgdl = (total_len / max(1, len(docs)))

    def search(self, query: str, *, top_k: int = 5) -> List[Tuple[int, float]]:
        q = tokenize(query)
        N = len(self.docs)
        scores: List[Tuple[int, float]] = []

        for i, d in enumerate(self.docs):
            dl = sum(self.tf[i].values())
            s = 0.0
            for term in q:
                if term not in self.tf[i]:
                    continue
                df = self.df.get(term, 0)
                # idf with BM25+
                idf = math.log((N - df + 0.5) / (df + 0.5) + 1.0)
                tf = self.tf[i][term]
                denom = tf + self.k1 * (1 - self.b + self.b * (dl / (self.avgdl or 1.0)))
                s += idf * (tf * (self.k1 + 1) / (denom or 1.0))
            scores.append((i, s))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

def load_jsonl(path: Path) -> List[dict]:
    out = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out

def metrics_for_one_query(ranked_doc_ids: List[str], relevant_ids: set, k: int) -> Tuple[float, float, float]:
    top = ranked_doc_ids[:k]
    rel_in_top = [d for d in top if d in relevant_ids]
    precision = len(rel_in_top) / k if k else 0.0
    recall = len(rel_in_top) / max(1, len(relevant_ids))
    # MRR@k: reciprocal rank of first relevant in top-k
    rr = 0.0
    for idx, d in enumerate(top, start=1):
        if d in relevant_ids:
            rr = 1.0 / idx
            break
    return precision, recall, rr

def main() -> int:
    corpus_rows = load_jsonl(CORPUS)
    gold_rows = load_jsonl(GOLD)

    # corpus docs keyed by section_id+lang
    corpus_by_key: Dict[Tuple[str, str], List[Doc]] = {}
    for r in corpus_rows:
        sid = (r.get("section_id") or "").strip()
        lang = (r.get("language") or "ru").strip().lower()
        if not sid:
            continue
        d = Doc(
            doc_id=str(r.get("doc_id", "")),
            section_id=sid,
            language=lang,
            text=str(r.get("text", ""))[:5000],
        )
        corpus_by_key.setdefault((sid, lang), []).append(d)

    # gold queries: берем только те, у которых section_id проставлен
    eval_gold = []
    for r in gold_rows:
        sid = (r.get("section_id") or "").strip()
        lang = (r.get("language") or "ru").strip().lower()
        if not sid or sid not in EVAL_SECTION_IDS:
            continue
        text = str(r.get("text", ""))
        if len(text) < 120:
            continue
        eval_gold.append((sid, lang, build_query_from_gold(text)))

    if not eval_gold:
        raise SystemExit(
            "No gold rows with section_id found. "
            "Fill gold_sections.jsonl['section_id'] at least for payment_terms/delivery_terms."
        )

    for sid in sorted(EVAL_SECTION_IDS):
        for lang in ("ru", "en"):
            key = (sid, lang)
            docs = corpus_by_key.get(key, [])
            if len(docs) < 10:
                continue

            idx = BM25Index(k1=1.5, b=0.75)
            idx.add(docs)

            # relevant set = все документы этого section_id+lang в корпусе
            relevant_ids = {d.doc_id + "::" + d.section_id + "::" + d.language + f"::{i}" for i, d in enumerate(docs)}
            # чтобы id были уникальны, используем индекс i (иначе doc_id может повторяться)
            doc_uid = [d.doc_id + "::" + d.section_id + "::" + d.language + f"::{i}" for i, d in enumerate(docs)]

            # queries только для нужного sid/lang
            queries = [q for (s2, l2, q) in eval_gold if s2 == sid and l2 == lang]
            if not queries:
                continue

            agg = {k: {"p": 0.0, "r": 0.0, "mrr": 0.0, "n": 0} for k in TOP_KS}

            for q in queries:
                hits = idx.search(q, top_k=max(TOP_KS))
                ranked = [doc_uid[i] for i, _ in hits]

                for k in TOP_KS:
                    p, r, rr = metrics_for_one_query(ranked, relevant_ids, k)
                    agg[k]["p"] += p
                    agg[k]["r"] += r
                    agg[k]["mrr"] += rr
                    agg[k]["n"] += 1

            print(f"\n=== RETRIEVAL BM25 baseline: section_id={sid}, lang={lang}, queries={len(queries)}, docs={len(docs)} ===")
            for k in TOP_KS:
                n = agg[k]["n"]
                print(
                    f"k={k:>2}  "
                    f"Precision@k={agg[k]['p']/n:.3f}  "
                    f"Recall@k={agg[k]['r']/n:.3f}  "
                    f"MRR@k={agg[k]['mrr']/n:.3f}"
                )

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
