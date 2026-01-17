from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List


def _norm_spaces(s: str) -> str:
    s = (s or "").replace("\u00A0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _pick_snippets(precedents: List[str], *, max_snippets: int = 6) -> List[str]:
    
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


@dataclass
class PaymentTermsParams:
    payment_trigger: str                # invoice_date / acceptance_date / delivery_date / etc.
    payment_term_days: int
    prepayment_required: bool
    bank_details_included: bool
    withholding_allowed: bool
    suspension_right: bool
    bank_charges: str                   # payer / beneficiary / shared
    vat_mode: str                       # exclusive_if_any / inclusive / not_applicable
    late_payment_penalty_enabled: bool


def _get_payment_block(form_input: dict) -> dict:
    p = (form_input or {}).get("payment")
    if isinstance(p, dict):
        return p
    return {}


def _parse_params(form_input: dict) -> PaymentTermsParams:
    """
    Парсинг из form_input["payment"].
    Если какого-то поля нет — ставим по дефолту.
    """
    p = _get_payment_block(form_input)

    return PaymentTermsParams(
        payment_trigger=str(p.get("payment_trigger", "invoice_date")),
        payment_term_days=int(p.get("payment_term_days", 30)),
        prepayment_required=bool(p.get("prepayment_required", False)),
        bank_details_included=bool(p.get("bank_details_included", False)),
        withholding_allowed=bool(p.get("withholding_allowed", False)),
        suspension_right=bool(p.get("suspension_right", False)),
        bank_charges=str(p.get("bank_charges", "payer")),
        vat_mode=str(p.get("vat_mode", "exclusive_if_any")),
        late_payment_penalty_enabled=bool(p.get("late_payment_penalty_enabled", False)),
    )



# Язык / Шаблоны

def _lang(form_input: dict) -> str:
    return str((form_input or {}).get("language_mode", "ru")).strip().lower()


TEXT = {
    "ru": {
        "intro": 'Ты — помощник юриста. Сгенерируй раздел договора "Порядок расчетов".',
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
        "intro": 'You are a legal assistant. Generate the contract section "Payment Terms".',
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



# Утилиты

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
# Двуязычные блоки
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


def _structure_requirements(form_input: dict) -> list[str]:
    
    if _lang(form_input) == "en":
        return [
            "Section structure:",
            "- 20–30 numbered subclauses.",
            "- Format: strictly 1.1., 1.2., 1.3., ... (each on a new line).",
            "- Each subclause must be a complete legal sentence.",
            "- Do not repeat subclauses (no semantic duplicates).",
            "- Each clause must start with a different grammatical construction wherever reasonably possible.",
        ]
    return [
        "Структура раздела:",
        "- 20–30 подпунктов.",
        "- Формат: строго 1.1., 1.2., 1.3., ... (каждый с новой строки).",
        "- Каждый подпункт — одно законченное юридическое предложение.",
        "- Не повторяй подпункты (никаких смысловых дублей).",
        "- Каждый подпункт должен начинаться с разных грамматических конструкций где это возможно"
    ]


def _forbidden_topics(form_input: dict) -> list[str]:
    
    if _lang(form_input) == "en":
        return [
            "Do NOT mention (these belong to other contract sections):",
            "- Disputes, court/arbitration, claims procedures.",
            "- Notices as a separate section/mechanism.",
            "- General liability/remedies/indemnities.",
            "- Changing bank details procedure (especially when bank_details_included=false).",
        ]
    return [
        "Запрещено упоминать (это другие секции договора):",
        "- Споры/арбитраж/суд/претензии/претензионный порядок/переговоры.",
        "- Уведомления как отдельный порядок (notices).",
        "- Убытки/возмещение убытков/общая ответственность (liability/remedies).",
        "- Изменение банковских реквизитов/обязанность сообщать реквизиты (особенно при bank_details_included=false).",
    ]


def _constraints(form_input: dict, p: PaymentTermsParams) -> list[str]:
    
    base_en = [
        "Do not copy factual details from precedents (amounts, currencies, rates, clause numbers, company names, bank details).",
        "Use only what is provided by the Input Form parameters.",
        "Avoid repetition: each idea must appear only once.",
        "No placeholders like [AMOUNT]/[CURRENCY]/[TERM_DAYS] in the final text.",
        "Do NOT start more than three clauses with the same introductory phrase.",
        "Vary the grammatical subject and sentence structure across clauses.",
    ]
    base_ru = [
        "Не копируй факты и реквизиты из прецедентов (суммы, валюты, ставки, номера пунктов, названия компаний/стран, банковские реквизиты).",
        "Все условия и переключатели берутся ТОЛЬКО из Input Form.",
        "Не повторяй предложения и фразы: каждое утверждение должно появляться только один раз.",
        "Не используй плейсхолдеры вида [AMOUNT]/[CURRENCY]/[TERM_DAYS] в финальном тексте.",
    ]

    if not p.bank_details_included:
        if _lang(form_input) == "en":
            base_en.append("Do NOT include bank details (you may state that bank details are provided elsewhere in the contract/annex).")
        else:
            base_ru.append("Не добавляй банковские реквизиты (можно указать, что реквизиты приведены в договоре/приложении).")

    if not p.late_payment_penalty_enabled:
        if _lang(form_input) == "en":
            base_en.append("Do NOT add penalties/interest for late payment (unless explicitly enabled by the Input Form).")
        else:
            base_ru.append("Не добавляй штрафы/пени/проценты за просрочку оплаты (если не включено формой).")

    return base_en if _lang(form_input) == "en" else base_ru


def _topic_plan(form_input: dict, p: PaymentTermsParams) -> list[str]:
    # План тем под 20+ подпунктов
    if _lang(form_input) == "en":
        return [
            "Allowed topics (cover all; 1 topic = 1 subclause, no repetition):",
            "1) Basis for payment (invoice).",
            f"2) Payment term: {p.payment_term_days} days {_trigger_phrase(form_input, p.payment_trigger)}.",
            "3) Definition of payment date (choose ONE: debit from Buyer OR credit to Supplier, not both).",
            "4) Payment method (bank transfer / cashless).",
            f"5) Prepayment: {'required' if p.prepayment_required else 'not required'}.",
            f"6) Withholding/set-off: {'allowed' if p.withholding_allowed else 'not allowed unless agreed'}.",
            f"7) Bank charges: {_bank_charges_phrase(form_input, p.bank_charges)}.",
            f"8) VAT: {_vat_mode_phrase(form_input, p.vat_mode)}.",
            "9) Invoicing format (electronic copies allowed; generic).",
            "10) Invoice issuance timing (generic; no numbers from precedents).",
            "11) Supporting documents evidencing delivery/acceptance for payment (generic).",
            "12) Reconciliation statement possibility (act of reconciliation).",
            "13) Procedure for correcting an invoice (credit note/corrective invoice) – generic.",
            "14) Overpayment handling (set-off/refund) – generic.",
            "15) Payment for partial deliveries (if applicable) – generic.",
            "16) Currency clause (generic; no currency codes unless provided in form).",
            "17) Prohibition/allowance of deductions (restate once; avoid duplicates).",
            "18) Suspension right upon late payment (only if enabled).",
            "19) Disputed amounts handling (only payment mechanics, no disputes section).",
            "20) Record-keeping / confirmations of payment (generic).",
            "If you need 20–30 items: split the above procedures into smaller steps WITHOUT introducing new contract sections.",
        ]

    return [
        "Разрешённые темы (покрой все; 1 тема = 1 подпункт, без повторов):",
        "1) Основание оплаты: счет/инвойс.",
        f"2) Срок оплаты: {p.payment_term_days} дней {_trigger_phrase(form_input, p.payment_trigger)}.",
        "3) Момент исполнения обязательства по оплате: выбери ОДНУ дефиницию (списание ИЛИ зачисление) и используй её везде.",
        "4) Форма расчетов: безналичный порядок (без реквизитов).",
        f"5) Предоплата: {'требуется' if p.prepayment_required else 'не требуется'}.",
        f"6) Удержания/зачеты (withholding/set-off): {'разрешены' if p.withholding_allowed else 'не допускаются, если иное не согласовано'}.",
        f"7) Банковские комиссии: {_bank_charges_phrase(form_input, p.bank_charges)}.",
        f"8) НДС/VAT: {_vat_mode_phrase(form_input, p.vat_mode)}.",
        "9) Формат выставления счетов: допускается электронная форма/копии (общо).",
        "10) Срок выставления счета после отгрузки/приемки (общо, без чисел из прецедентов).",
        "11) Документы-основания для оплаты (общо: накладная/акт, без реквизитов).",
        "12) Сверка взаиморасчетов: возможность/порядок акта сверки.",
        "13) Корректировочные документы: корректировочный счет/инвойс (общо).",
        "14) Переплата: возврат/зачет по согласованию сторон (общо).",
        "15) Оплата частичных поставок/этапов (если применимо) — общо.",
        "16) Валюта платежа (общо; не указывать валюту, если нет в форме).",
        "17) Запрет/допустимость удержаний — ровно один раз, без дублей.",
        "18) Просрочка оплаты: право приостановления (только если включено формой).",
        "19) Оспариваемые суммы: механизм оплаты неоспариваемой части (без раздела про споры).",
        "20) Подтверждение оплаты и хранение платежных документов (общо).",
        "Если нужно 20–30 подпунктов: дроби процедуры на шаги, НЕ добавляя новые разделы договора.",
    ]



# Конструктор промптов

def build_payment_terms_prompt(form_input: dict, precedents_clean: List[str]) -> str:
    """
    Двуязычный промпт для локальной LLM: генерация раздела Payment Terms с использованием 
    параметров из входной формы и подсказок из прецедентов.
    """
    p = _parse_params(form_input)
    snippets = _pick_snippets(precedents_clean, max_snippets=6)

    party_vocab = _party_vocab(form_input)
    
    if _lang(form_input) == "en":
        requirements = [
            f"- Payment term: {p.payment_term_days} days {_trigger_phrase(form_input, p.payment_trigger)}.",
            f"- Prepayment: {'required' if p.prepayment_required else 'not required'}.",
            f"- Withholding / set-off: {'allowed' if p.withholding_allowed else 'not allowed unless otherwise agreed'}.",
            f"- Suspension right upon late payment: {'enabled' if p.suspension_right else 'not granted'}.",
            f"- Bank charges: {_bank_charges_phrase(form_input, p.bank_charges)}.",
            f"- VAT: {_vat_mode_phrase(form_input, p.vat_mode)}.",
            f"- Late payment penalty/interest: {'include' if p.late_payment_penalty_enabled else 'do not include'}.",
            f"- Bank details included in contract: {'yes' if p.bank_details_included else 'no'}.",
        ]
    else:
        requirements = [
            f"- Срок оплаты: {p.payment_term_days} дней {_trigger_phrase(form_input, p.payment_trigger)}.",
            f"- Предоплата: {'требуется' if p.prepayment_required else 'не требуется'}.",
            f"- Удержания/зачеты (withholding): {'разрешены' if p.withholding_allowed else 'не допускаются, если иное не согласовано'}.",
            f"- Приостановление исполнения при просрочке: {'право есть' if p.suspension_right else 'право не предоставляется'}.",
            f"- Банковские комиссии: {_bank_charges_phrase(form_input, p.bank_charges)}.",
            f"- НДС/VAT: {_vat_mode_phrase(form_input, p.vat_mode)}.",
            f"- Неустойка/проценты за просрочку оплаты: {'включить' if p.late_payment_penalty_enabled else 'не включать'}.",
            f"- Банковские реквизиты включены в договор: {'да' if p.bank_details_included else 'нет'}.",
        ]

    mandatory_structure = (
        f"{_T(form_input, 'mandatory')}\n"
        "- The section MUST contain AT LEAST 20 numbered subclauses.\n"
        "- Format: strictly 1.1., 1.2., 1.3., ...\n"
        "- Each subclause must be on a new line.\n"
        "- Each subclause must be a complete legal sentence.\n"
        "- Do NOT merge multiple conditions into one subclause.\n"
        "- If in doubt, add additional subclauses.\n"
        if _lang(form_input) == "en" else
        f"{_T(form_input, 'mandatory')}\n"
        "- Раздел ДОЛЖЕН содержать НЕ МЕНЕЕ 20 подпунктов.\n"
        "- Формат подпунктов: строго 1.1., 1.2., 1.3., ...\n"
        "- Каждый подпункт — с новой строки.\n"
        "- Каждый подпункт — одно законченное юридическое предложение.\n"
        "- НЕЛЬЗЯ объединять несколько условий в один подпункт.\n"
        "- Если сомневаешься, добавь дополнительные подпункты.\n"
    )

    structure_requirements = _structure_requirements(form_input)
    topic_plan = _topic_plan(form_input, p)
    forbidden_topics = _forbidden_topics(form_input)
    constraints = _constraints(form_input, p)

    return _norm_spaces(
        f"""
{_T(form_input, "intro")}

{mandatory_structure}

{_T(form_input, "params")}
{chr(10).join(requirements)}

{_T(form_input, "party_terms")}
{chr(10).join(f"- {x}" for x in party_vocab)}

{_T(form_input, "structure")}
{chr(10).join(structure_requirements)}

{_T(form_input, "topic_plan")}
{chr(10).join(topic_plan)}

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

