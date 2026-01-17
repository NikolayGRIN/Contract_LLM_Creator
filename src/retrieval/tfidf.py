from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# ----------------------------
# Data model
# ----------------------------
@dataclass
class Clause:
    doc_id: str
    section_group: str
    section_id: str
    language: str
    text: str
    score: float = 0.0


# ----------------------------
# Corpus loading
# ----------------------------
def load_corpus_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


# ----------------------------
# Query builders
# ----------------------------
def build_payment_terms_query(language: str, form: dict) -> str:
    """
    Build a natural-language query for TF-IDF based on form fields.
    This is deliberately redundant — redundancy improves TF-IDF recall.
    """
    lang = (language or "ru").lower()

    if lang == "en":
        parts = [
            "payment terms",
            "price and payment",
            "invoice",
            "currency",
            "payment deadline",
            "bank transfer",
            "advance payment",
            "settlement",
        ]
        if "total_amount" in form:
            parts.append("total amount")
        return " ".join(parts)

    # default: ru
    parts = [
        "условия оплаты",
        "цена и порядок расчетов",
        "порядок оплаты",
        "срок оплаты",
        "валюта платежа",
        "безналичный расчет",
        "банковский перевод",
        "предоплата",
        "окончательный расчет",
    ]
    if "total_amount" in form:
        parts.append("общая стоимость договора")
    return " ".join(parts)


# ----------------------------
# TF-IDF retrieval
# ----------------------------
def tfidf_retrieve(
    clauses: List[Clause],
    query: str,
    *,
    k: int = 20,
    n_return: int = 3,
) -> List[Clause]:
    """
    Rank clauses by cosine similarity(query, clause.text).
    """
    if not clauses:
        return []

    texts = [c.text for c in clauses]

    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.9,
        stop_words=None,  # legal text → no aggressive stopwords
    )

    tfidf_matrix = vectorizer.fit_transform(texts)
    query_vec = vectorizer.transform([query])

    sims = cosine_similarity(query_vec, tfidf_matrix)[0]

    for c, s in zip(clauses, sims):
        c.score = float(s)

    clauses_sorted = sorted(clauses, key=lambda c: c.score, reverse=True)

    return clauses_sorted[:n_return]