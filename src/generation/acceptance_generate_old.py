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


def build_acceptance_prompt(form_input: dict, precedents_clean: Optional[List[str]] = None) -> str:
    lang = _lang(form_input)
    acc = (form_input or {}).get("acceptance") or {}

    required = acc.get("acceptance_required", True)
    period_days = acc.get("acceptance_period_days", "TBD")
    doc = acc.get("acceptance_document", "tbd")
    rules = acc.get("acceptance_rules", "tbd")
    docs_required = acc.get("documents_required")

    if lang == "en":
        base = (
            "Write the section ACCEPTANCE AND INSPECTION.\n"
            "Use these parameters:\n"
            f"- Acceptance required: {required}\n"
            f"- Acceptance period (days): {period_days}\n"
            f"- Acceptance document: {doc}\n"
            f"- Acceptance rules: {rules}\n"
            f"- Documents required: {docs_required}\n"
            "Requirements:\n"
            "- Describe inspection on delivery, discrepancy notice, defects handling.\n"
            "- If acceptance_required=false, keep it lightweight (no strict mandatory acceptance act).\n"
            "- Do not invent exact addresses or numbers.\n"
            "- Do NOT add any numbering like '1.' or '6.2.1.'. Numbering will be added automatically.\n"
            "- Do NOT output the section title as a separate line.\n"
            "- Each point must be a separate line, one complete legal sentence per line.\n"
            "Output ONLY the section text.\n"
        )
    else:
        base = (
            "Напиши раздел ПРИЕМКА И ИНСПЕКЦИЯ.\n"
            "Используй параметры:\n"
            f"- Приемка требуется: {required}\n"
            f"- Срок приемки (дней): {period_days}\n"
            f"- Документ приемки: {doc}\n"
            f"- Правила приемки: {rules}\n"
            f"- Перечень документов: {docs_required}\n"
            "Требования:\n"
            "- Опиши порядок осмотра при поставке, уведомление о несоответствиях, порядок по дефектам.\n"
            "- Если acceptance_required=false — не делай акт обязательным условием для приемки.\n"
            "- Не придумывай адреса и номера документов.\n"            
            "- НЕ выводи заголовок раздела отдельной строкой.\n"
            "- Каждый пункт — отдельной строкой, одно законченное юридическое предложение.\n"
            "Выведи ТОЛЬКО текст раздела.\n"
            "Пиши только на русском языке.\n"
        )

    return base + _snippets_block(lang, precedents_clean)