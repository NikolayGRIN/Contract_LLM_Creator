from __future__ import annotations

from typing import List, Optional


def _lang(form_input: dict) -> str:
    return str((form_input or {}).get("language_mode", "ru")).strip().lower()


def _val(x):
    """Hide empty / TBD-like values to avoid polluting prompt."""
    if x in (None, "", "tbd", "TBD"):
        return None
    return x


def _fmt_list(xs) -> Optional[str]:
    if not xs:
        return None
    out = []
    for x in xs:
        x = _val(x)
        if x is None:
            continue
        out.append(str(x))
    return ", ".join(out) if out else None


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


def build_liability_prompt(form_input: dict, precedents_clean: Optional[List[str]] = None) -> str:
    lang = _lang(form_input)

    liab = (form_input or {}).get("liability") or {}
    comm = (form_input or {}).get("commercial") or {}

    cap_enabled = bool(liab.get("liability_cap_enabled", True))
    cap_type = _val(liab.get("liability_cap_type"))
    cap_scope = _val(liab.get("cap_scope"))
    indirect_excl = bool(liab.get("indirect_damages_excluded", True))

    exceptions = _fmt_list(liab.get("exceptions_to_cap", []))
    delay_penalty_enabled = bool(liab.get("delay_in_delivery_penalty_enabled", False))
    claim_days = _val(liab.get("claim_notice_days"))

    currency = _val(comm.get("currency") or (form_input or {}).get("currency"))
    price = _val(comm.get("contract_price"))

    # NOTE: Do NOT let "TBD" appear; if missing -> say "not specified"
    if lang == "en":
        base = (
            "Draft the section LIABILITY AND PENALTIES for an equipment supply contract.\n"
            "Use ONLY the provided facts and do not invent new ones.\n\n"
            "FACTS:\n"
            f"- Liability cap enabled: {cap_enabled}\n"
            f"- Cap type: {cap_type}\n"
            f"- Cap scope: {cap_scope}\n"
            f"- Indirect damages excluded: {indirect_excl}\n"
            f"- Exceptions to cap: {exceptions}\n"
            f"- Delay in delivery penalty enabled: {delay_penalty_enabled}\n"
            f"- Claim notice days: {claim_days}\n"
            f"- Currency: {currency}\n"
            f"- Contract price: {price}\n\n"
            "REQUIREMENTS:\n"
            "- One complete legal sentence per line.\n"
            "- Do NOT add numbering or headings.\n"
            "- If Contract price is not specified, describe the cap conceptually (e.g., 'up to the Contract Price') without numbers.\n"
            "- If delay penalty is disabled, do NOT introduce any specific penalty rate or amount.\n"
            "- Keep remedies/penalties strictly within this section (no disputes/arbitration clauses).\n"
            "- Output ONLY the section text.\n"
        )
    else:
        base = (
            "Сформулируй раздел «ОТВЕТСТВЕННОСТЬ И ШТРАФЫ» договора поставки оборудования.\n"
            "Используй ТОЛЬКО указанные факты и не выдумывай новые.\n\n"
            "ФАКТЫ:\n"
            f"- Лимит ответственности включён: {cap_enabled}\n"
            f"- Тип лимита: {cap_type}\n"
            f"- Объём лимита: {cap_scope}\n"
            f"- Косвенные убытки исключены: {indirect_excl}\n"
            f"- Исключения из лимита: {exceptions}\n"
            f"- Неустойка за просрочку поставки включена: {delay_penalty_enabled}\n"
            f"- Срок уведомления о претензии (дней): {claim_days}\n"
            f"- Валюта: {currency}\n"
            f"- Цена договора: {price}\n\n"
            "ТРЕБОВАНИЯ:\n"
            "- Одно юридически завершённое предложение на строку.\n"
            "- Без нумерации и без заголовков.\n"
            "- Если цена договора не задана — описывай лимит концептуально («в пределах цены договора») без сумм.\n"
            "- Если неустойка за просрочку поставки выключена — не вводи конкретные ставки/суммы штрафа.\n"
            "- Не добавляй порядок разрешения споров/арбитраж (это другая секция).\n"
            "- Выведи ТОЛЬКО текст раздела.\n"
            "Пиши только на русском языке.\n"
        )

    return base + _snippets_block(lang, precedents_clean)
