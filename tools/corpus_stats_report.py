from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# =========================================
# CONFIG
# =========================================
CORPUS_PATH = Path("data/corpus_sections.jsonl")
OUT_DIR = Path("debug")
OUT_DIR.mkdir(exist_ok=True)

# -----------------------------------------
# Порядок секций (как ты просил)
# -----------------------------------------
RU_ORDER = [
    "definitions",
    "subject_of_contract",
    "price_and_taxes",
    "payment_terms",
    "delivery_terms",
    "acceptance_and_inspection",
    "warranties",
    "liability_and_penalties",
    "force_majeure",
    "governing_law_and_disputes",
]
RU_LABELS = [
    "ОПРЕДЕЛЕНИЯ",
    "ПРЕДМЕТ ДОГОВОРА",
    "ЦЕНА И НАЛОГИ",
    "УСЛОВИЯ ОПЛАТЫ",
    "УСЛОВИЯ ПОСТАВКИ",
    "ПРИЕМКА И ИНСПЕКЦИЯ",
    "ГАРАНТИИ",
    "ОТВЕТСТВЕННОСТЬ И ШТРАФЫ",
    "ФОРС-МАЖОР",
    "ПРИМЕНИМОЕ ПРАВО И СПОРЫ",
]

EN_ORDER = RU_ORDER[:]  # section_id одинаковые, отличаются только подписи
EN_LABELS = [
    "DEFINITIONS",
    "SUBJECT OF CONTRACT",
    "PRICE AND TAXES",
    "PAYMENT TERMS",
    "DELIVERY TERMS",
    "ACCEPTANCE AND INSPECTION",
    "WARRANTIES",
    "LIABILITY AND PENALTIES",
    "FORCE MAJEURE",
    "GOVERNING LAW AND DISPUTES",
]

# -----------------------------------------
# Палитра “как на твоих слайдах” (10 цветов)
# Порядок должен совпадать с RU_ORDER/EN_ORDER
# -----------------------------------------
PALETTE = [
    "#4F81BD",  # blue
    "#C0504D",  # red
    "#9BBB59",  # green
    "#8064A2",  # purple
    "#4BACC6",  # cyan
    "#F79646",  # orange
    "#95B3D7",  # light blue
    "#DA9694",  # pink
    "#C3D69B",  # light green
    "#B1A0C7",  # lilac
]

# -----------------------------------------
# Стиль заголовков (как у тебя)
# -----------------------------------------
TITLE_COLOR = "#1F4E79"  # темно-синий
TITLE_SIZE = 32
SUBTITLE_SIZE = 18


# =========================================
# Helpers
# =========================================
def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def tokenize_simple(text: str) -> list[str]:
    # важно: это “псевдо-токены” по словам, а не токены LLM
    return re.findall(r"[A-Za-zА-Яа-я0-9]+", (text or "").lower())


def bar_with_labels(ax, x, y, colors, value_fmt="{:.0f}", value_fontsize=13):
    bars = ax.bar(x, y, color=colors, width=0.42)
    ymax = float(np.max(y)) if len(y) else 1.0
    pad = ymax * 0.02

    for b, v in zip(bars, y):
        ax.text(
            b.get_x() + b.get_width() / 2.0,
            float(v) + pad,
            value_fmt.format(float(v)),
            ha="center",
            va="bottom",
            fontsize=value_fontsize,
            fontweight="bold",
            color="black",
        )
    return bars


def finalize_axes(ax, *, ylabel: str, xticklabels: list[str], rotate: int):
    ax.set_ylabel(ylabel, fontsize=16)
    ax.tick_params(axis="y", labelsize=14)
    ax.tick_params(axis="x", labelsize=13)
    ax.set_xticks(range(len(xticklabels)))
    ax.set_xticklabels(xticklabels, rotation=rotate, ha="right")

    # сетка как на примере
    ax.yaxis.grid(True, linestyle="-", linewidth=1.0, alpha=0.25)
    ax.set_axisbelow(True)


def save_fig_no_clip(fig, out_path: Path):
    # ключ к “не обрезать” подписи
    fig.savefig(out_path, dpi=200, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)


# =========================================
# LOAD + FEATURES
# =========================================
rows = read_jsonl(CORPUS_PATH)
df = pd.DataFrame(rows)

# ожидаемые поля: language, section_id, text
df["text"] = df.get("text", "").fillna("")
df["language"] = df.get("language", "").fillna("")
df["section_id"] = df.get("section_id", "").fillna("")

df["tokens"] = df["text"].apply(lambda x: len(tokenize_simple(x)))

# нормализуем язык
df["language"] = df["language"].str.lower().replace({"rus": "ru", "eng": "en"})


# =========================================
# AGGREGATES (count + avg_tokens) per lang
# =========================================
def get_counts(lang: str, order: list[str]) -> np.ndarray:
    s = df[df["language"] == lang].groupby("section_id")["text"].count()
    return np.array([int(s.get(sec, 0)) for sec in order], dtype=float)


def get_avg_tokens(lang: str, order: list[str]) -> np.ndarray:
    s = df[df["language"] == lang].groupby("section_id")["tokens"].mean()
    return np.array([float(s.get(sec, 0.0)) for sec in order], dtype=float)


ru_counts = get_counts("ru", RU_ORDER)
en_counts = get_counts("en", EN_ORDER)

ru_avg_toks = get_avg_tokens("ru", RU_ORDER)
en_avg_toks = get_avg_tokens("en", EN_ORDER)

# одинаковые шкалы
counts_max = max(float(np.max(ru_counts)), float(np.max(en_counts)), 1.0)
tokens_max = max(float(np.max(ru_avg_toks)), float(np.max(en_avg_toks)), 1.0)

# “красивые” верхние границы (округлим вверх до 10/50)
def nice_top(v: float, step: int) -> int:
    return int(np.ceil(v / step) * step)

counts_top = nice_top(counts_max * 1.05, step=10)   # +5% запас
tokens_top = nice_top(tokens_max * 1.05, step=50)   # +5% запас


# =========================================
# PLOT 1: Distribution by sections (RU/EN)
# =========================================
fig = plt.figure(figsize=(16, 9))

# общий заголовок
fig.suptitle(
    "Распределение корпуса по секциям",
    fontsize=TITLE_SIZE,
    fontweight="bold",
    color=TITLE_COLOR,
    y=0.97,
)

# две оси
ax1 = fig.add_axes([0.06, 0.18, 0.41, 0.66])  # left, bottom, width, height
ax2 = fig.add_axes([0.54, 0.18, 0.41, 0.66])

ax1.set_title("RU", fontsize=20, fontweight="bold")
ax2.set_title("EN", fontsize=20, fontweight="bold")

x = np.arange(len(RU_ORDER))

bar_with_labels(ax1, x, ru_counts, PALETTE, value_fmt="{:.0f}", value_fontsize=13)
bar_with_labels(ax2, x, en_counts, PALETTE, value_fmt="{:.0f}", value_fontsize=13)

finalize_axes(ax1, ylabel="Количество", xticklabels=RU_LABELS, rotate=55)
finalize_axes(ax2, ylabel="Количество", xticklabels=EN_LABELS, rotate=55)

ax1.set_ylim(0, counts_top)
ax2.set_ylim(0, counts_top)

save_fig_no_clip(fig, OUT_DIR / "sections_distribution_matched_scales_noclip.png")


# =========================================
# PLOT 2: Average section length (tokens)
# =========================================
fig = plt.figure(figsize=(16, 9))
fig.suptitle(
    "Средняя длина секций (слова)",
    fontsize=TITLE_SIZE,
    fontweight="bold",
    color=TITLE_COLOR,
    y=0.97,
)

ax1 = fig.add_axes([0.06, 0.18, 0.41, 0.66])
ax2 = fig.add_axes([0.54, 0.18, 0.41, 0.66])

ax1.set_title("RU", fontsize=20, fontweight="bold")
ax2.set_title("EN", fontsize=20, fontweight="bold")

bar_with_labels(ax1, x, ru_avg_toks, PALETTE, value_fmt="{:.1f}", value_fontsize=13)
bar_with_labels(ax2, x, en_avg_toks, PALETTE, value_fmt="{:.1f}", value_fontsize=13)

finalize_axes(ax1, ylabel="Avg tokens", xticklabels=RU_LABELS, rotate=55)
finalize_axes(ax2, ylabel="Avg tokens", xticklabels=EN_LABELS, rotate=55)

ax1.set_ylim(0, tokens_top)
ax2.set_ylim(0, tokens_top)

save_fig_no_clip(fig, OUT_DIR / "avg_tokens_matched_scales_noclip.png")


print("✅ Saved:")
print(" -", OUT_DIR / "sections_distribution_matched_scales_noclip.png")
print(" -", OUT_DIR / "avg_tokens_matched_scales_noclip.png")
