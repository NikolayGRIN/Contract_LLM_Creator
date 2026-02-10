# src/generation/payment_terms_generate.py
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional
from src.prompts.topic_checklists import get_section_checklist


# # =========================================================
# # Topic diversity checklist (anti-duplication control)
# # =========================================================
# PAYMENT_TERMS_TOPIC_CHECKLIST = {
#     "ru": """
# === ТРЕБОВАНИЕ К РАЗНООБРАЗИЮ СОДЕРЖАНИЯ ===
# Каждый подпункт должен раскрывать НОВЫЙ аспект условий оплаты.
# НЕЛЬЗЯ повторять или перефразировать одну и ту же тему.

# Покрой РАЗНЫЕ аспекты, например:

# • основание для оплаты (счет/инвойс/акт)
# • срок оплаты и порядок исчисления дней
# • момент исполнения обязательства по оплате
# • валюта платежа
# • банковские комиссии
# • порядок выставления счетов
# • подтверждающие документы
# • частичная/поэтапная оплата
# • корректировочные счета
# • оспаривание сумм
# • запрет или условия удержаний/зачетов
# • возврат переплаты
# • сверка взаиморасчетов
# • подтверждение платежей
# • электронный документооборот
# • иные финансовые процедуры БЕЗ повторов

# ВАЖНО: каждый подпункт = новая самостоятельная идея.
# """,
#     "en": """
# === CONTENT DIVERSITY REQUIREMENT (MANDATORY) ===
# Each subclause must describe a DIFFERENT aspect of Payment Terms.
# Do NOT repeat or paraphrase the same topic.

# Cover DISTINCT aspects such as:

# • payment trigger
# • term calculation
# • moment of payment completion
# • currency
# • bank charges
# • invoicing procedure
# • supporting documents
# • partial/milestone payments
# • corrective invoices
# • disputed amounts
# • withholding/set-off rules
# • overpayment refunds
# • reconciliation
# • confirmations
# • e-documents
# • other financial procedures WITHOUT repetition

# IMPORTANT: every subclause must introduce a NEW rule.
# """
# }


def _norm_spaces(s: str) -> str:
    s = (s or "").replace("\u00A0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _pick_snippets(precedents: List[str], *, max_snippets: int = 6) -> List[str]:
    """
    Берём короткие "полезные" фразы из прецедентов как подсказки стилю.
    Только формулировки; факты брать нельзя (суммы/валюта/ставки/номера пунктов/реквизиты).
    """
    if not precedents:
        return []

    keywords = [
        # RU
        "оплат", "платеж", "платёж", "счет", "счёт", "инвойс", "invoice",
        "дата оплаты", "датой оплаты", "банковск", "комисси", "ндс", "vat",
        "предоплат", "аванс", "удержан", "withholding", "приостанов",
        "suspension", "пен", "неустойк", "штраф", "процент", "просроч",
        # EN
        "payment", "invoice", "due", "payable", "bank", "transfer",
        "vat", "interest", "penalty", "setoff", "set-off", "withholding",
    ]

    out: List[str] = []
    seen = set()

    for p in precedents:
        text = re.sub(r"\s+", " ", (p or "")).strip()
        if not text:
            continue

        sents = re.split(r"(?<=[.!?])\s+", text)
        for s in sents:
            s2 = s.strip()
            if "[" in s2 or "]" in s2:
                continue
            if len(s2) < 60 or len(s2) > 240:
                continue
            low = s2.lower()
            if not any(k in low for k in keywords):
                continue
            if low in seen:
                continue
            seen.add(low)
            out.append(s2)
            if len(out) >= max_snippets:
                return out

    return out


# ------------------------------
# Form mapping (your schema)
# ------------------------------
@dataclass
class PaymentTermsParams:
    payment_trigger: str
    payment_term_days: int
    currency: str   
    prepayment_percent: int
    bank_details_included: bool
    withholding_allowed: bool
    suspension_right: bool
    bank_charges: str
    vat_mode: str
    late_payment_penalty_enabled: bool


def _get_payment_block(form_input: dict) -> dict:
    p = (form_input or {}).get("payment")
    if isinstance(p, dict):
        return p
    return {}


# def _parse_float_percent(v) -> float | None:
#     """
#     Принимаем:
#       - 30 / 30.0
#       - "30" / "30.0" / "30%" / "30 %"
#       - None
#     Возвращаем float (0..100 не принуждаем здесь; можно добавить clamp при желании).
#     """
#     if v is None:
#         return None
#     if isinstance(v, (int, float)):
#         return float(v)
#     if isinstance(v, str):
#         s = v.strip().replace(",", ".")
#         s = s.replace("%", "").strip()
#         if not s:
#             return None
#         try:
#             return float(s)
#         except ValueError:
#             return None
#     return None


def _parse_params(form_input: dict) -> PaymentTermsParams:
    """
    Строгий парсинг из form_input["payment"].
    """
    p = _get_payment_block(form_input)

    commercial = (form_input or {}).get("commercial") or {}
    currency = (
        p.get("payment_currency")
        or p.get("currency")
        or commercial.get("currency")
        or (form_input or {}).get("currency")
        or "USD"
    )

    # prepayment_percent = _parse_float_percent(p.get("prepayment_percent"))

    return PaymentTermsParams(
        payment_trigger=str(p.get("payment_trigger", "invoice_date")),
        payment_term_days=int(p.get("payment_term_days", 30)),
        currency=str(currency),       
        prepayment_percent = p.get("prepayment_percent"),
        bank_details_included=bool(p.get("bank_details_included", False)),
        withholding_allowed=bool(p.get("withholding_allowed", False)),
        suspension_right=bool(p.get("suspension_right", False)),
        bank_charges=str(p.get("bank_charges", "payer")),
        vat_mode=str(p.get("vat_mode", "exclusive_if_any")),
        late_payment_penalty_enabled=bool(p.get("late_payment_penalty_enabled", False)),
    )


# ----------------------------
# Language / templates
# ----------------------------
def _lang(form_input: dict) -> str:
    return str((form_input or {}).get("language_mode", "ru")).strip().lower()


TEXT = {
    "ru": {
        "intro": 'Ты — помощник юриста. Сгенерируй раздел договора "УСЛОВИЯ ОПЛАТЫ".',
        "mandatory": "ОБЯЗАТЕЛЬНЫЕ ТРЕБОВАНИЯ К СТРУКТУРЕ:",
        "params": "Параметры (обязательно соблюдай):",
        "party_terms": "Термины сторон (обязательно соблюдай):",
        "structure": "Структурные требования (обязательно соблюдай):",
        "topic_plan": "План тем (обязательно соблюдай):",
        "forbidden": "Запрещённые темы (обязательно соблюдай):",
        "snippets": "Фразы-ориентиры (ТОЛЬКО стиль/формулировки, не факты):",
        "constraints": "Ограничения:",
        "only_text": "Сгенерируй ТОЛЬКО текст раздела (без заголовка).",
        "write_lang": "Пиши на русском.",
        "no_snippets": "- (нет)",
    },
    "en": {
        "intro": 'You are a legal assistant. Generate the contract section "PAYMENT TERMS".',
        "mandatory": "MANDATORY STRUCTURE REQUIREMENTS:",
        "params": "Parameters (must follow):",
        "party_terms": "Party terms (must follow consistently):",
        "structure": "Structural requirements (must follow):",
        "topic_plan": "Topic plan (must cover, no repetition):",
        "forbidden": "Forbidden topics (do NOT mention):",
        "snippets": "Stylistic hints (style only, not facts):",
        "constraints": "Constraints:",
        "only_text": "Generate ONLY the section text (without a heading).",
        "write_lang": "Write in English.",
        "no_snippets": "- (none)",
    },
}


def _T(form_input: dict, key: str) -> str:
    lang = _lang(form_input)
    if lang not in TEXT:
        lang = "ru"
    return TEXT[lang][key]


def _output_language_instruction(form_input: dict) -> str:
    return _T(form_input, "write_lang")


# ----------------------------
# Phrase helpers
# ----------------------------
def _trigger_phrase(form_input: dict, trigger: str) -> str:
    t = (trigger or "").lower().strip()

    if _lang(form_input) == "en":
        mapping = {
            "invoice_date": "from the invoice date",
            "receipt_of_invoice": "from the date of receipt of the invoice",
            "acceptance_date": "from the acceptance date (signing of acceptance documents)",
            "delivery_date": "from the delivery/dispatch date",
            "signing_date": "from the contract signing date",
        }
        return mapping.get(t, "from the agreed triggering event (invoice/acceptance/delivery)")

    mapping = {
        "invoice_date": "с даты выставления счета/инвойса",
        "receipt_of_invoice": "с даты получения счета/инвойса",
        "acceptance_date": "с даты подписания документов, подтверждающих приемку",
        "delivery_date": "с даты поставки (отгрузки) товара",
        "signing_date": "с даты подписания договора",
    }
    return mapping.get(t, "с даты наступления согласованного события (invoice/acceptance/delivery)")


def _bank_charges_phrase(form_input: dict, bank_charges: str) -> str:
    t = (bank_charges or "").lower().strip()

    if _lang(form_input) == "en":
        mapping = {
            "payer": "bank charges are borne by the paying party",
            "beneficiary": "bank charges are borne by the receiving party",
            "shared": "bank charges are shared as agreed by the Parties",
        }
        return mapping.get(t, "bank charges are allocated as agreed by the Parties")

    mapping = {
        "payer": "банковские комиссии несет плательщик",
        "beneficiary": "банковские комиссии несет получатель",
        "shared": "банковские комиссии распределяются между Сторонами по согласованию",
    }
    return mapping.get(t, "банковские комиссии распределяются в соответствии с применимой практикой и согласованием Сторон")


def _vat_mode_phrase(form_input: dict, vat_mode: str) -> str:
    t = (vat_mode or "").lower().strip()

    if _lang(form_input) == "en":
        mapping = {
            "exclusive_if_any": "VAT is added on top of the price, if applicable",
            "inclusive": "VAT is included in the price, if applicable",
            "not_applicable": "VAT is not applicable",
        }
        return mapping.get(t, "VAT applies (or not) in accordance with applicable law")

    mapping = {
        "exclusive_if_any": "НДС/VAT начисляется сверх цены, если подлежит применению",
        "inclusive": "НДС/VAT включен в цену, если подлежит применению",
        "not_applicable": "НДС/VAT не применяется",
    }
    return mapping.get(t, "НДС/VAT применяется (или не применяется) в соответствии с применимым законодательством")


# ----------------------------
# Bilingual blocks
# ----------------------------
def _party_vocab(form_input: dict) -> list[str]:
    if _lang(form_input) == "en":
        return [
            'Use party terms consistently across the entire section: "Buyer" and "Supplier".',
            'Do NOT mix party labels such as "Customer", "Seller", "Contractor" if you already use "Buyer/Supplier".',
        ]
    return [
        "Используй термины Сторон единообразно по всему тексту: «Покупатель» и «Поставщик».",
        "НЕ используй в этой секции термины «Заказчик», «Исполнитель», «Продавец», если уже используешь «Покупатель/Поставщик».",
    ]


# def _structure_requirements(form_input: dict) -> list[str]:
#     if _lang(form_input) == "en":
#         return [
#             "Section structure:",
#             "20–30 subclauses.",
#             "Each subclause must be a complete legal sentence.",
#             "One sentence per line.",
#             "IMPORTANT: Do NOT repeat numbering inside the line (no '4.1. 4.1 ...'); after the number, start immediately with words.",
#             "Do not repeat subclauses (no semantic duplicates).",
#             "Vary sentence openings; avoid starting many lines with the same phrase.",
#         ]
#     return [
#         "Структура раздела:",
#         "20–30 подпунктов.",
#         "Каждый подпункт — одно законченное юридическое предложение.",
#         "Одно предложение на строке.",
#         "ВАЖНО: НЕ дублируй номер внутри строки (нельзя «4.1. 4.1 ...»); после номера сразу начинается текст словами.",
#         "Не повторяй подпункты (никаких смысловых дублей).",
#         "Разнообразь начала предложений; не начинай много строк одной и той же фразой.",
#     ]


def _forbidden_topics(form_input: dict) -> list[str]:
    if _lang(form_input) == "en":
        return [
            "Do NOT mention:",
            "- Disputes, court/arbitration, claims procedures.",           
            "- General liability/remedies/indemnities.",
        ]
    return [
        "Запрещено упоминать:",
        "- Споры/арбитраж/суд/претензии/претензионный порядок/переговоры.",        
        "- Убытки/возмещение убытков/общая ответственность (liability/remedies).",
    ]


def _constraints(form_input: dict, p: PaymentTermsParams) -> list[str]:
    base_en = [
        "Use ONLY what is provided by the Input Form parameters.",
        "Do not copy factual details from precedents (amounts, currencies, rates, clause numbers, company names, bank details).",
        "No placeholders like [AMOUNT]/[CURRENCY]/[TERM_DAYS] in the final text.",
        "Moment of payment: choose ONE definition and use it consistently (prefer credit to Supplier account).",
        "No repetition: each idea must appear only once.",
        "Do NOT start more than three subclauses with the same introductory phrase.",
        "Do NOT repeat numbering inside a line (no '4.1. 4.1 ...').",
    ]
    base_ru = [
        "Все условия и переключатели берутся ТОЛЬКО из Input Form.",
        "Не копируй факты и реквизиты из прецедентов (суммы, валюты, ставки, номера пунктов, названия компаний/стран, банковские реквизиты).",
        "Не используй плейсхолдеры вида [AMOUNT]/[CURRENCY]/[TERM_DAYS] в финальном тексте.",
        "Момент оплаты: выбери ОДНУ дефиницию и используй её везде (предпочтительно зачисление на счет Поставщика).",
        "Не повторяй мысли: каждое утверждение — только один раз.",
        "Не начинай более 3 подпунктов одной и той же стартовой фразой.",
        "Не дублируй нумерацию внутри строки (нельзя «4.1. 4.1 ...»).",
    ]

    if not p.bank_details_included:
        if _lang(form_input) == "en":
            base_en.append("Do NOT include bank details (you may state bank details are provided elsewhere in the contract/annex).")
        else:
            base_ru.append("Не добавляй банковские реквизиты (можно указать, что реквизиты приведены в договоре/приложении).")

    if not p.late_payment_penalty_enabled:
        if _lang(form_input) == "en":
            base_en.append("Do NOT add penalties/interest for late payment (unless explicitly enabled by the Input Form).")
        else:
            base_ru.append("Не добавляй штрафы/пени/проценты за просрочку оплаты (если не включено формой).")

    if not p.suspension_right:
        if _lang(form_input) == "en":
            base_en.append("Do NOT grant suspension rights if the Input Form disables it.")
        else:
            base_ru.append("Не добавляй право приостановления, если оно выключено формой.")

    return base_en if _lang(form_input) == "en" else base_ru


def _topic_plan(form_input: dict, p: PaymentTermsParams) -> list[str]:
    
    if _lang(form_input) == "en":
        return [
            "Parameter-dependent rules (must be reflected):",
            f"- Payment term: {p.payment_term_days} days {_trigger_phrase(form_input, p.payment_trigger)}.",
            "- Payment date definition: choose ONE (debit from Buyer OR credit to Supplier) and use consistently.",
            f"- Prepayment: {p.prepayment_percent}% of the Contract Price.",
            f"- Withholding/set-off: {'allowed' if p.withholding_allowed else 'not allowed unless otherwise agreed'}.",
            f"- Bank charges: {_bank_charges_phrase(form_input, p.bank_charges)}.",
            f"- VAT: {_vat_mode_phrase(form_input, p.vat_mode)}.",
            f"- Payment currency: {p.currency}.",
            "Write in English ONLY.",
            "If you need 20–30 items: split the above procedures into smaller steps WITHOUT introducing new contract sections.",
        ]

    return [
        "Разрешённые темы (покрой все; 1 тема = 1 подпункт, без повторов):",
        "Параметризованные правила (обязательно отрази):",
        f"- Срок оплаты: {p.payment_term_days} дней {_trigger_phrase(form_input, p.payment_trigger)}.",
        "- Момент оплаты: выбери ОДНУ дефиницию (списание ИЛИ зачисление) и используй везде.",
        f"- Предоплата: {p.prepayment_percent}% контрактной стоимости.",
        f"- Удержания/зачеты: {'разрешены' if p.withholding_allowed else 'не допускаются, если иное не согласовано'}.",
        f"- Банковские комиссии: {_bank_charges_phrase(form_input, p.bank_charges)}.",
        f"- НДС/VAT: {_vat_mode_phrase(form_input, p.vat_mode)}.",
        f"- Валюта платежа: {p.currency}.",
        "Если нужно 20–30 подпунктов: дроби процедуры на шаги, НЕ добавляя новые разделы договора.",
        "Пиши только на русском языке.",
    ]

# ----------------------------
# Prompt builder
# ----------------------------
def build_payment_terms_prompt(form_input: dict, precedents_clean: List[str]) -> str:
    """
    Bilingual prompt for local LLM: generate Payment Terms section
    using Input Form parameters + stylistic hints from precedents.
    """
    p = _parse_params(form_input)
    snippets = _pick_snippets(precedents_clean, max_snippets=6)
    party_vocab = _party_vocab(form_input)
    lang = _lang(form_input)

    # Explicit requirements so the model doesn't invent facts
    if lang == "en":
        requirements = [
            f"- Payment term: {p.payment_term_days} days {_trigger_phrase(form_input, p.payment_trigger)}.",           
            f"- Prepayment: {p.prepayment_percent}% of the Contract Price.",
            f"- Withholding / set-off: {'allowed' if p.withholding_allowed else 'not allowed unless otherwise agreed'}.",
            f"- Suspension right upon late payment: {'enabled' if p.suspension_right else 'not granted'}.",
            f"- Bank charges: {_bank_charges_phrase(form_input, p.bank_charges)}.",
            f"- VAT: {_vat_mode_phrase(form_input, p.vat_mode)}.",
            f"- Late payment penalty/interest: {'include' if p.late_payment_penalty_enabled else 'do not include'}.",
            f"- Payment currency: {p.currency}.",
        ]
    else:
        requirements = [
            f"- Срок оплаты: {p.payment_term_days} дней {_trigger_phrase(form_input, p.payment_trigger)}.",
            f"- Предоплата: {p.prepayment_percent}% контрактной стоимости.",
            f"- Удержания/зачеты (withholding): {'разрешены' if p.withholding_allowed else 'не допускаются, если иное не согласовано'}.",
            f"- Приостановление исполнения при просрочке: {'право есть' if p.suspension_right else 'право не предоставляется'}.",
            f"- Банковские комиссии: {_bank_charges_phrase(form_input, p.bank_charges)}.",
            f"- НДС/VAT: {_vat_mode_phrase(form_input, p.vat_mode)}.",
            f"- Неустойка/проценты за просрочку оплаты: {'включить' if p.late_payment_penalty_enabled else 'не включать'}.",
            f"- Валюта платежа: {p.currency}.",
        ]

    # IMPORTANT: We generate WITHOUT heading; run_generate adds numbering later.
    # We also explicitly prohibit duplicating numbering inside a line to avoid "4.1. 4.1 ..."
    if lang == "en":
        mandatory_structure = (
            f"{_T(form_input, 'mandatory')}\n"
            "- The section MUST contain AT LEAST 20 subclauses.\n"
            "- Each subclause must be on a new line.\n"
            "- Each subclause must be a complete legal sentence.\n"
            "- One sentence per line.\n"
            "- Do NOT repeat numbering inside a line (no '4.1. 4.1 ...').\n"
            "- If you output any numbering, it must appear ONLY ONCE at the very beginning of the line.\n"
        )
    else:
        mandatory_structure = (
            f"{_T(form_input, 'mandatory')}\n"
            "- Раздел ДОЛЖЕН содержать НЕ МЕНЕЕ 20 подпунктов.\n"
            "- Каждый подпункт — с новой строки.\n"
            "- Каждый подпункт — одно законченное юридическое предложение.\n"
            "- Одно предложение на строке.\n"
            "- НЕ дублируй нумерацию внутри строки (нельзя «4.1. 4.1 ...»).\n"
            "- Если выводишь нумерацию, она должна быть ТОЛЬКО ОДИН РАЗ в начале строки.\n"
            "- Пиши только на русском языке.\n"
        )

    # structure_requirements = _structure_requirements(form_input)
    topic_plan = _topic_plan(form_input, p)
    forbidden_topics = _forbidden_topics(form_input)
    constraints = _constraints(form_input, p)
    diversity_block = get_section_checklist("payment_terms", lang) or ""

    return _norm_spaces(
        f"""
{_T(form_input, "intro")}

{mandatory_structure}

{_T(form_input, "params")}
{chr(10).join(requirements)}

{_T(form_input, "party_terms")}
{chr(10).join(f"- {x}" for x in party_vocab)}

{_T(form_input, "topic_plan")}
{chr(10).join(topic_plan)}

{diversity_block}

{_T(form_input, "forbidden")}
{chr(10).join(forbidden_topics)}

{_T(form_input, "snippets")}
{chr(10).join(f"- {s}" for s in snippets) if snippets else _T(form_input, "no_snippets")}

{_T(form_input, "constraints")}
{chr(10).join(f"- {c}" for c in constraints)}

{_T(form_input, "only_text")}
{_output_language_instruction(form_input)}
"""
    )
