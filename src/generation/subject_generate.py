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


def build_subject_prompt(form_input: dict, precedents_clean: Optional[List[str]] = None) -> str:
    lang = _lang(form_input)
    goods = (form_input or {}).get("goods") or {}
    goods_desc = goods.get("goods_description") or "TBD"
    qty = goods.get("quantity") or "TBD"
    spec_ref = goods.get("specification_ref") or "TBD"

    if lang == "en":
        base = (
            "Write the section SUBJECT OF CONTRACT for a supply contract.\n"
            "Use these parameters:\n"
            f"- Goods description: {goods_desc}\n"
            f"- Quantity: {qty}\n"
            f"- Specification reference: {spec_ref}\n"
            "Requirements:\n"
            "- Describe Seller's obligation to supply and Buyer's obligation to accept and pay.\n"
            "- Refer to specification/appendix if provided.\n"
            "- Avoid real addresses, bank details, exact serial numbers (unless given).\n"
            "Output ONLY the section text.\n"
        )
    else:
        base = (
            "Напиши раздел ПРЕДМЕТ ДОГОВОРА для договора поставки.\n"
            "Используй параметры:\n"
            f"- Описание товара: {goods_desc}\n"
            f"- Количество: {qty}\n"
            f"- Ссылка на спецификацию: {spec_ref}\n"
            "Требования:\n"
            "- Опиши обязанность Поставщика поставить, а Покупателя принять и оплатить.\n"
            "- Сошлись на спецификацию/приложение, если указано.\n"
            "- Не добавляй адреса/реквизиты/серийные номера, которых нет во входных данных.\n"
            "НЕ включать гарантию, ответственность, оплату, маркировку, упаковку"
            "Формат строго:\n"            
            "- Каждый подпункт 1–2 строки, без подзаголовков и без markdown.\n"
            "Выведи ТОЛЬКО текст раздела.\n"
            "Пиши только на русском языке.\n"
        )

    return base + _snippets_block(lang, precedents_clean)
