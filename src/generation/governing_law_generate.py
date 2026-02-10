from __future__ import annotations

from typing import List, Optional


def _lang(form_input: dict) -> str:
    return str((form_input or {}).get("language_mode", "ru")).strip().lower()


def _val(x):
    if x in (None, "", "tbd", "TBD", "null"):
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


def build_governing_law_prompt(form_input: dict, precedents_clean: Optional[List[str]] = None) -> str:
    lang = _lang(form_input)
    legal = (form_input or {}).get("legal") or {}

    governing_law = _val(legal.get("governing_law"))
    dispute = _val(legal.get("dispute_resolution"))
    court_place = _val(legal.get("court_place"))
    arbitration_seat = _val(legal.get("arbitration_seat"))

    if lang == "en":
        base = (
            "Draft the section GOVERNING LAW AND DISPUTES for an equipment supply contract.\n"
            "Use ONLY the provided facts and do not invent new ones.\n\n"
            "FACTS:\n"
            f"- Governing law: {governing_law}\n"
            f"- Dispute resolution mode: {dispute}\n"
            f"- Court place: {court_place}\n"
            f"- Arbitration seat (if any): {arbitration_seat}\n\n"
            "REQUIREMENTS:\n"
            "- One complete legal sentence per line.\n"
            "- Do NOT add numbering or headings.\n"
            "- If governing law is not specified, state it generically as 'the law agreed by the Parties / applicable law' (without naming a country).\n"
            "- If dispute resolution mode is not specified, keep it neutral: negotiations, then competent court (no city/country).\n"
            "- If mode is state_court: refer to competent courts; mention court_place only if provided.\n"
            "- If mode is arbitration: refer to arbitration seated in arbitration_seat only if provided; do NOT invent institutions (ICC/LCIA/etc.).\n"
            "- If mode is negotiation_then_court: include a short negotiation stage and then court.\n"
            "- Keep the pre-claim stage lightweight (written notice/negotiation) without turning it into a separate Notices section.\n"
            "- Output ONLY the section text.\n"
        )
    else:
        base = (
            "Сформулируй раздел «ПРИМЕНИМОЕ ПРАВО И РАЗРЕШЕНИЕ СПОРОВ» договора поставки оборудования.\n"
            "Используй ТОЛЬКО указанные факты и не выдумывай новые.\n\n"
            "ФАКТЫ:\n"
            f"- Применимое право: {governing_law}\n"
            f"- Режим разрешения споров: {dispute}\n"
            f"- Место суда: {court_place}\n"
            f"- Место/seat арбитража (если есть): {arbitration_seat}\n\n"
            "ТРЕБОВАНИЯ:\n"
            "- Одно юридически завершённое предложение на строку.\n"
            "- Без нумерации и без заголовков.\n"
            "- Если применимое право не задано — укажи общо «право, согласованное Сторонами / применимое право» без страны.\n"
            "- Если режим разрешения споров не задан — нейтрально: переговоры, затем компетентный суд (без города/страны).\n"
            "- Если режим = state_court — укажи компетентный суд; место суда упоминай только если оно задано.\n"
            "- Если режим = arbitration — укажи арбитраж; seat указывай только если задан; НЕ придумывай учреждения (МКАС/ICC/LCIA и т.п.).\n"
            "- Если режим = negotiation_then_court — добавь короткую переговорную/претензионную стадию, затем суд.\n"
            "- Претензионную стадию делай облегчённой, не превращай в отдельный раздел Notices.\n"
            "- Выведи ТОЛЬКО текст раздела.\n"
            "Пиши только на русском языке.\n"
        )

    return base + _snippets_block(lang, precedents_clean)
