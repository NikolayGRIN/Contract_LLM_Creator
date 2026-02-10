# src/generation/warranties_generate.py
from __future__ import annotations

from typing import List, Optional


# =========================================================
# helpers
# =========================================================
def _lang(form_input: dict) -> str:
    return str((form_input or {}).get("language_mode", "ru")).strip().lower()


def _val(x):
    """Hide empty / TBD-like values to avoid polluting prompt."""
    if x in (None, "", "tbd", "TBD"):
        return None
    return x


def _snippets_block(lang: str, precedents_clean: Optional[List[str]]) -> str:
    """
    STYLE ONLY examples (short, safe, deterministic).
    Used by embeddings retrieval results.
    """
    if not precedents_clean:
        return ""

    head = (
        "\n\n=== STYLE EXAMPLES (use ONLY style, do NOT copy details) ===\n"
        if lang == "en"
        else "\n\n=== ПРИМЕРЫ СТИЛЯ (только стиль, без копирования деталей) ===\n"
    )

    items = "\n".join(f"- {s.strip()[:500]}" for s in precedents_clean[:4])

    return head + items + "\n=== END ===\n"


# =========================================================
# MAIN BUILDER (EMBEDDINGS-READY)
# IMPORTANT:
#  • NO llama
#  • NO retrieval
#  • ONLY prompt text
# =========================================================
def build_warranties_prompt(
    form_input: dict,
    precedents_clean: Optional[List[str]] = None,
) -> str:

    lang = _lang(form_input)
    w = (form_input or {}).get("warranties") or {}

    months = _val(w.get("warranty_period_months"))
    start = _val(w.get("warranty_start"))
    remedy = _val(w.get("remedy"))
    response_days = _val(w.get("response_time_days"))

    if lang == "en":
        base = (
            "Draft the WARRANTIES section of an equipment supply contract.\n"
            "Use ONLY the provided facts and do not invent new ones.\n\n"
            "FACTS:\n"
            f"- Warranty period (months): {months}\n"
            f"- Warranty start: {start}\n"
            f"- Remedy: {remedy}\n"
            f"- Response time (days): {response_days}\n\n"
            "REQUIREMENTS:\n"
            "- Cover conformity to specifications, defects notification, remedy procedure, repair/replacement logistics.\n"
            "- One complete legal sentence per line.\n"
            "- Do NOT add numbering or headings.\n"
            "- Output ONLY the section text.\n"
        )
    else:
        base = (
            "Сформулируй раздел «ГАРАНТИИ» договора поставки оборудования.\n"
            "Используй ТОЛЬКО указанные факты и не выдумывай новые.\n\n"
            "ФАКТЫ:\n"
            f"- Срок гарантии (мес.): {months}\n"
            f"- Начало гарантии: {start}\n"
            f"- Способ устранения: {remedy}\n"
            f"- Срок реакции (дней): {response_days}\n\n"
            "ТРЕБОВАНИЯ:\n"
            "- Опиши соответствие спецификации, уведомление о дефектах, порядок ремонта/замены.\n"
            "- Одно юридически завершённое предложение на строку.\n"
            "- Без нумерации и без заголовков.\n"
            "- Выведи ТОЛЬКО текст раздела.\n"
            "Пиши только на русском языке.\n"
        )

    return base + _snippets_block(lang, precedents_clean)
