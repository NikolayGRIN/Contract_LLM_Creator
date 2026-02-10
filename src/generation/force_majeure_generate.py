from __future__ import annotations

from typing import List, Optional


def _lang(form_input: dict) -> str:
    return str((form_input or {}).get("language_mode", "ru")).strip().lower()


def _val(x):
    if x in (None, "", "tbd", "TBD"):
        return None
    return x


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


def build_force_majeure_prompt(form_input: dict, precedents_clean: Optional[List[str]] = None) -> str:
    lang = _lang(form_input)
    legal = (form_input or {}).get("legal") or {}

    notice_days = _val(legal.get("force_majeure_notice_days"))

    if lang == "en":
        base = (
            "Draft the section FORCE MAJEURE for an equipment supply contract.\n"
            "Use ONLY the provided facts and do not invent new ones.\n\n"
            "FACTS:\n"
            f"- Notice period (days): {notice_days}\n\n"
            "REQUIREMENTS:\n"
            "- One complete legal sentence per line.\n"
            "- Do NOT add numbering or headings.\n"
            "- If notice period is not specified, describe the notice duty generically without any numbers.\n"
            "- Cover: FM definition/events, notice, evidence, mitigation, suspension, extension, termination threshold.\n"
            "- No political statements; keep it contract-standard.\n"
            "- Output ONLY the section text.\n"
        )
    else:
        base = (
            "Сформулируй раздел «ФОРС-МАЖОР» договора поставки оборудования.\n"
            "Используй ТОЛЬКО указанные факты и не выдумывай новые.\n\n"
            "ФАКТЫ:\n"
            f"- Срок уведомления (дней): {notice_days}\n\n"
            "ТРЕБОВАНИЯ:\n"
            "- Одно юридически завершённое предложение на строку.\n"
            "- Без нумерации и без заголовков.\n"
            "- Если срок уведомления не задан — опиши обязанность уведомления общо, без цифр.\n"
            "- Покрой: определение FM/перечень событий, уведомление, подтверждающие документы, меры по минимизации, приостановление, продление сроков, порог для расторжения.\n"
            "- Никаких политических заявлений — только стандартные договорные формулировки.\n"
            "- Выведи ТОЛЬКО текст раздела.\n"
            "Пиши только на русском языке.\n"
        )

    return base + _snippets_block(lang, precedents_clean)
