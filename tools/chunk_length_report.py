from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt

META = Path("debug/emb_index_bge_m3/bge_m3_chunks_meta.jsonl")
OUT  = Path("debug/chunk_len_report")
OUT.mkdir(parents=True, exist_ok=True)

rows = []
with META.open("r", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        tok_len = int(r["tok_end"]) - int(r["tok_start"])
        rows.append({
            "section_id": r.get("section_id", ""),
            "language": r.get("language", ""),
            "doc_index": r.get("doc_index", -1),
            "chunk_index": r.get("chunk_index", -1),
            "tok_len": tok_len,
        })

df = pd.DataFrame(rows)

# 1) общая сводка
summary = df["tok_len"].describe(percentiles=[0.5, 0.9, 0.95]).to_frame("tok_len")
summary.to_csv(OUT / "summary_overall.csv")

# 2) по секциям (+ по языкам, если нужно)
by_section = (
    df.groupby(["language", "section_id"])["tok_len"]
    .agg(count="count", mean="mean", p50=lambda x: x.quantile(0.5),
         p90=lambda x: x.quantile(0.9), p95=lambda x: x.quantile(0.95),
         min="min", max="max")
    .round(2)
    .reset_index()
)
by_section.to_csv(OUT / "summary_by_section_lang.csv", index=False)

# 3) гистограмма (общая)
plt.figure(figsize=(10, 5))
plt.hist(df["tok_len"], bins=30)
plt.title("Распределение длины чанков (в токенах)")
plt.xlabel("tok_len")
plt.ylabel("count")
plt.tight_layout()
plt.savefig(OUT / "hist_overall.png", dpi=200)
plt.close()

# 4) отдельные гистограммы RU/EN
for lang in sorted(df["language"].dropna().unique()):
    sub = df[df["language"] == lang]
    if sub.empty:
        continue
    plt.figure(figsize=(10, 5))
    plt.hist(sub["tok_len"], bins=30)
    plt.title(f"Распределение длины чанков (в токенах) — {lang.upper()}")
    plt.xlabel("tok_len")
    plt.ylabel("count")
    plt.tight_layout()
    plt.savefig(OUT / f"hist_{lang}.png", dpi=200)
    plt.close()

print("OK:", OUT)
