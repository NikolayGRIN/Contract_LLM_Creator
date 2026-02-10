from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# =========================================
# CONFIG (все строим из готовых CSV)
# =========================================
SUMMARY_PATH = Path(r"debug\chunk_len_report\summary_by_section_lang.csv")
AVG_CHUNKS_PATH = Path(r"debug\avg_chunks_per_section.csv")  # читаем (можно использовать позже)
OUT_DIR = Path("debug")
OUT_DIR.mkdir(exist_ok=True)

# -----------------------------------------
# Порядок секций (как ты просил)
# -----------------------------------------
ORDER = [
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
TITLE_COLOR = "#1F4E79"
TITLE_SIZE = 32

# -----------------------------------------
# “Поля” графика (настройка руками)
# bottom больше => подписи снизу не режутся
# -----------------------------------------
AX_LEFT  = [0.06, 0.22, 0.41, 0.62]   # [left, bottom, width, height]
AX_RIGHT = [0.54, 0.22, 0.41, 0.62]
ROTATE_X = 55

# =========================================
# Helpers
# =========================================
def nice_top(v: float, step: int) -> int:
    v = float(v)
    if v <= 0:
        return step
    return int(np.ceil(v / step) * step)

def bar_with_labels(ax, x, y, colors, value_fmt="{:.0f}", value_fontsize=13):
    bars = ax.bar(x, y, color=colors, width=0.42)
    ymax = float(np.max(y)) if len(y) else 1.0
    pad = ymax * 0.02 if ymax > 0 else 1.0

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
    ax.yaxis.grid(True, linestyle="-", linewidth=1.0, alpha=0.25)
    ax.set_axisbelow(True)

def save_fig_no_clip(fig, out_path: Path):
    # bbox_inches + pad_inches — ключ к отсутствию обрезания
    fig.savefig(out_path, dpi=200, bbox_inches="tight", pad_inches=0.35)
    plt.close(fig)

def series_by_lang(df_sum: pd.DataFrame, lang: str, col: str, order: list[str]) -> np.ndarray:
    s = df_sum[df_sum["language"] == lang].set_index("section_id")[col]
    return np.array([float(s.get(sec, 0.0)) for sec in order], dtype=float)

# =========================================
# LOAD CSVs
# =========================================
if not SUMMARY_PATH.exists():
    raise FileNotFoundError(f"summary file not found: {SUMMARY_PATH}")

df_sum = pd.read_csv(SUMMARY_PATH)

# нормализуем язык/колонки
df_sum["language"] = df_sum["language"].astype(str).str.lower().replace({"rus": "ru", "eng": "en"})
df_sum["section_id"] = df_sum["section_id"].astype(str)

# гарантируем числовые типы
for c in ["count", "mean", "p50", "p90", "p95", "min", "max"]:
    if c in df_sum.columns:
        df_sum[c] = pd.to_numeric(df_sum[c], errors="coerce").fillna(0)

# avg_chunks_per_section читаем (не обязателен для графиков 1-3)
df_chunks = None
if AVG_CHUNKS_PATH.exists():
    df_chunks = pd.read_csv(AVG_CHUNKS_PATH)

# =========================================
# DATA ARRAYS
# =========================================
ru_counts = series_by_lang(df_sum, "ru", "count", ORDER)
en_counts = series_by_lang(df_sum, "en", "count", ORDER)

ru_mean = series_by_lang(df_sum, "ru", "mean", ORDER)
en_mean = series_by_lang(df_sum, "en", "mean", ORDER)

ru_p90 = series_by_lang(df_sum, "ru", "p90", ORDER)
en_p90 = series_by_lang(df_sum, "en", "p90", ORDER)

# одинаковые шкалы
counts_top = nice_top(max(np.max(ru_counts), np.max(en_counts), 1.0) * 1.05, step=10)
mean_top   = nice_top(max(np.max(ru_mean),   np.max(en_mean),   1.0) * 1.05, step=50)
p90_top    = nice_top(max(np.max(ru_p90),    np.max(en_p90),    1.0) * 1.05, step=50)

x = np.arange(len(ORDER))

# =========================================
# PLOT 1: Distribution by sections (RU/EN)
# =========================================
fig = plt.figure(figsize=(16, 9))
fig.suptitle("Распределение корпуса по секциям", fontsize=TITLE_SIZE, fontweight="bold",
             color=TITLE_COLOR, y=0.97)

ax1 = fig.add_axes(AX_LEFT)
ax2 = fig.add_axes(AX_RIGHT)
ax1.set_title("RU", fontsize=20, fontweight="bold")
ax2.set_title("EN", fontsize=20, fontweight="bold")

bar_with_labels(ax1, x, ru_counts, PALETTE, value_fmt="{:.0f}", value_fontsize=13)
bar_with_labels(ax2, x, en_counts, PALETTE, value_fmt="{:.0f}", value_fontsize=13)

finalize_axes(ax1, ylabel="Количество", xticklabels=RU_LABELS, rotate=ROTATE_X)
finalize_axes(ax2, ylabel="Количество", xticklabels=EN_LABELS, rotate=ROTATE_X)
ax1.set_ylim(0, counts_top)
ax2.set_ylim(0, counts_top)

save_fig_no_clip(fig, OUT_DIR / "plot_1_sections_distribution.png")

# =========================================
# PLOT 2: Average section length (tokens) = mean
# =========================================
fig = plt.figure(figsize=(16, 9))
fig.suptitle("Средняя длина секций (токены)", fontsize=TITLE_SIZE, fontweight="bold",
             color=TITLE_COLOR, y=0.97)

ax1 = fig.add_axes(AX_LEFT)
ax2 = fig.add_axes(AX_RIGHT)
ax1.set_title("RU", fontsize=20, fontweight="bold")
ax2.set_title("EN", fontsize=20, fontweight="bold")

bar_with_labels(ax1, x, ru_mean, PALETTE, value_fmt="{:.1f}", value_fontsize=13)
bar_with_labels(ax2, x, en_mean, PALETTE, value_fmt="{:.1f}", value_fontsize=13)

finalize_axes(ax1, ylabel="Avg tokens", xticklabels=RU_LABELS, rotate=ROTATE_X)
finalize_axes(ax2, ylabel="Avg tokens", xticklabels=EN_LABELS, rotate=ROTATE_X)
ax1.set_ylim(0, mean_top)
ax2.set_ylim(0, mean_top)

save_fig_no_clip(fig, OUT_DIR / "plot_2_avg_tokens_mean.png")

# =========================================
# PLOT 3: P90 section length (tokens)
# =========================================
fig = plt.figure(figsize=(16, 9))
fig.suptitle("P90 длина секций (токены)", fontsize=TITLE_SIZE, fontweight="bold",
             color=TITLE_COLOR, y=0.97)

ax1 = fig.add_axes(AX_LEFT)
ax2 = fig.add_axes(AX_RIGHT)
ax1.set_title("RU", fontsize=20, fontweight="bold")
ax2.set_title("EN", fontsize=20, fontweight="bold")

bar_with_labels(ax1, x, ru_p90, PALETTE, value_fmt="{:.0f}", value_fontsize=13)
bar_with_labels(ax2, x, en_p90, PALETTE, value_fmt="{:.0f}", value_fontsize=13)

finalize_axes(ax1, ylabel="P90 tokens", xticklabels=RU_LABELS, rotate=ROTATE_X)
finalize_axes(ax2, ylabel="P90 tokens", xticklabels=EN_LABELS, rotate=ROTATE_X)
ax1.set_ylim(0, p90_top)
ax2.set_ylim(0, p90_top)

save_fig_no_clip(fig, OUT_DIR / "plot_3_p90_tokens.png")

print("✅ Saved plots:")
print(" -", OUT_DIR / "plot_1_sections_distribution.png")
print(" -", OUT_DIR / "plot_2_avg_tokens_mean.png")
print(" -", OUT_DIR / "plot_3_p90_tokens.png")

if df_chunks is not None:
    print("ℹ avg_chunks_per_section.csv loaded (not plotted yet):", AVG_CHUNKS_PATH)
