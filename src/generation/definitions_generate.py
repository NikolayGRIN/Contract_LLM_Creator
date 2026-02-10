from __future__ import annotations

from typing import List, Optional


def _lang(form_input: dict) -> str:
    return str((form_input or {}).get("language_mode", "ru")).strip().lower()


def _snippets_block(lang: str, precedents_clean: Optional[List[str]]) -> str:
    if not precedents_clean:
        return ""
    head = (
        "\n\n=== STYLE EXAMPLES (use ONLY style, do NOT copy details) ===\n"
        if lang == "en"
        else "\n\n=== ПРИМЕРЫ СТИЛЯ (только стиль, без копирования деталей) ===\n"
    )
    items = "\n".join(f"- {s.strip()[:500]}" for s in precedents_clean[:4])
    return head + items + "\n=== END ===\n"


def build_definitions_prompt(form_input: dict, precedents_clean: Optional[List[str]] = None) -> str:
    lang = _lang(form_input)

    if lang == "en":
        base = (
            "Write the section DEFINITIONS for a supply contract.\n"
            "Requirements:\n"
            "- Provide 10–14 concise legal definitions.\n"
            "- Use bullet list or numbered list.\n"
            "- Definitions must be generic (no real addresses, bank details, clause numbers).\n"
            "- Use Party terms: Seller / Buyer.\n"
            "Output ONLY the section text.\n"
        )
    else:
        base = (
            "Напиши раздел ОПРЕДЕЛЕНИЯ для договора поставки.\n"
            "Требования:\n"
            "- Дай 10–14 кратких юридических определений.\n"
            "- Можно маркированным или нумерованным списком.\n"
            "- Определения должны быть общими (без адресов, реквизитов, номеров пунктов).\n"
            "- Используй термины сторон: Поставщик / Покупатель.\n"
            "Выведи ТОЛЬКО текст раздела.\n"
        )

    return base + _snippets_block(lang, precedents_clean)
