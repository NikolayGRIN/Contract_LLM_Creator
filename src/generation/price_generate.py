from __future__ import annotations

from typing import List, Optional


def _lang(form_input: dict) -> str:
    return str((form_input or {}).get("language_mode", "ru")).strip().lower()

VAT_MODE_RU = {
    "exclusive_if_any": "НДС не применяется (спецрежим/освобождение), если иное не требуется законом",
    "exclusive": "НДС не применяется (если иное не требуется законом)",
    "inclusive": "НДС включён в цену",
    "additional": "НДС начисляется сверх цены",
    "not_applicable": "НДС не применяется",
    "vat_exempt": "освобождение от НДС",
    "tbd": "TBD",
    "TBD": "TBD",
}

VAT_MODE_EN = {
    "exclusive_if_any": "VAT not applicable unless required by law",
    "exclusive": "VAT exclusive (unless required by law)",
    "inclusive": "VAT included in the price",
    "additional": "VAT added on top of the price",
    "not_applicable": "VAT not applicable",
    "vat_exempt": "VAT exempt",
    "tbd": "TBD",
    "TBD": "TBD",
}

def normalize_vat_mode(vat_mode: str, *, lang: str) -> str:
    vm = str(vat_mode or "").strip()
    if not vm:
        return "TBD"
    key = vm.lower()
    if lang == "en":
        return VAT_MODE_EN.get(key, vm)
    return VAT_MODE_RU.get(key, vm)

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


def build_price_prompt(form_input: dict, precedents_clean: Optional[List[str]] = None) -> str:
    lang = _lang(form_input)
    commercial = (form_input or {}).get("commercial") or {}
    currency = commercial.get("currency") or (form_input or {}).get("currency") or "TBD"
    price = commercial.get("contract_price") or "TBD"
    vat_mode_raw = commercial.get("vat_mode") or (form_input or {}).get("payment", {}).get("vat_mode") or "tbd"
    vat_mode = normalize_vat_mode(vat_mode_raw, lang=lang)
    price_basis = commercial.get("price_basis") or "tbd"
    packaging = commercial.get("price_includes_packaging")

    if lang == "en":
        base = (
            "Write the section PRICE AND TAXES.\n"
            "Use these parameters:\n"
            f"- Currency: {currency}\n"
            f"- Contract price: {price}\n"
            f"- VAT mode: {vat_mode}\n"
            f"- Price basis: {price_basis}\n"
            f"- Price includes packaging: {packaging}\n"
            "Requirements:\n"
            "- If price is 'TBD', state that the price will be agreed in the Specification/Appendix or invoices.\n"
            "- Describe VAT handling according to VAT mode.\n"
            "- Avoid inventing tax rates, exact numbers, or bank details.\n"
            "- Begin subclauses from different phrases. Do NOT repeat the same phrases.\n"
            "Output ONLY the section text.\n"
        )
    else:
        base = (
            "Напиши раздел ЦЕНА И НАЛОГИ (НДС).\n"
            "Используй параметры:\n"
            f"- Валюта: {currency}\n"
            f"- Цена договора: {price}\n"
            f"- Режим НДС: {vat_mode}\n"
            f"- База цены: {price_basis}\n"
            f"- Цена включает упаковку: {packaging}\n"
            "Требования:\n"
            "- Если цена 'TBD', укажи, что цена/стоимость согласуется в Спецификации/Приложении или в счетах.\n"
            "- Опиши порядок учета НДС согласно режиму.\n"
            "- Не придумывай ставки, суммы и прочую конкретику.\n"
            "- Выведи ТОЛЬКО текст раздела.\n"
            "- Начинай подпункты разными фразами. НЕ повторяй предложения\n"
            "- Пиши только на русском языке.\n"
        )

    return base + _snippets_block(lang, precedents_clean)
