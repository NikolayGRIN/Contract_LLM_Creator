# src/generation/delivery_terms_generate.py
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List
from src.prompts.topic_checklists import get_section_checklist


def _norm_spaces(s: str) -> str:
    s = (s or "").replace("\u00A0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _pick_snippets(precedents: List[str], *, max_snippets: int = 6) -> List[str]:
    """
    Берём короткие "полезные" фразы из прецедентов как подсказки стилю.
    Только формулировки; факты брать нельзя (адреса/точные даты/Incoterms/номера).
    """
    if not precedents:
        return []

    keywords = [
        # RU
        "поставк", "отгруз", "доставк", "срок", "график", "парт",
        "частичн", "упаков", "маркир", "перевоз", "транспорт",
        "погруз", "разгруз", "рис", "право собственности", "приемк", "акт", "накладн",
        "склад", "место поставки", "передач",
        # EN
        "delivery", "dispatch", "shipment", "shipping", "lead time", "schedule",
        "partial", "packaging", "marking", "transport", "carrier",
        "loading", "unloading", "risk", "title", "acceptance", "delivery note",
        "warehouse", "delivery point",
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
            if len(s2) < 60 or len(s2) > 260:
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


# ----------------------------
# Form mapping (minimal / conservative)
# ----------------------------
@dataclass
class DeliveryTermsParams:
    delivery_term_months: None
    delivery_trigger: str
    partial_deliveries_allowed: bool
    delivery_place: str
    incoterms: str
    risk_transfer: str
    acceptance_docs: str
    packaging_required: bool


def _get_delivery_block(form_input: dict) -> dict:
    d = (form_input or {}).get("delivery")
    if isinstance(d, dict):
        return d
    return {}


def _parse_params(form_input: dict) -> DeliveryTermsParams:
    """
    Консервативные дефолты. Если поля нет — ставим безопасное значение.   
    """
    d = _get_delivery_block(form_input)

    
    raw_months = (
        d.get("delivery_within_months")  # v2
        if d.get("delivery_within_months") is not None
        else d.get("delivery_term_months")  # legacy
    )

    delivery_term_months = int(raw_months) if raw_months is not None else None

    delivery_trigger = str(d.get("delivery_date_type", "within_months_from_effective"))

    # частичные поставки
    partial_allowed = bool(d.get("partial_shipments_allowed", True))

    # место поставки
    delivery_place = str(d.get("delivery_place", "в согласованное место поставки"))

    # необязательные поля: если появятся в форме — будут использованы
    incoterms = str(d.get("incoterms", ""))
    risk_transfer = str(d.get("risk_transfer", "upon_delivery"))
    acceptance_docs = str(d.get("acceptance_document", ""))  # например: "act"
    packaging_required = bool(d.get("packaging_required", True))

    return DeliveryTermsParams(
        delivery_term_months=delivery_term_months,
        delivery_trigger=delivery_trigger,
        partial_deliveries_allowed=partial_allowed,
        delivery_place=delivery_place,
        incoterms=incoterms,
        risk_transfer=risk_transfer,
        acceptance_docs=acceptance_docs,
        packaging_required=packaging_required,
    )


# ----------------------------
# Language / templates
# ----------------------------
def _lang(form_input: dict) -> str:
    return str((form_input or {}).get("language_mode", "ru")).strip().lower()


TEXT = {
    "ru": {
        "intro": 'Ты — помощник юриста. Сгенерируй раздел договора "Условия поставки".',
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
        "intro": 'You are a legal assistant. Generate the contract section "Delivery Terms".',
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
def _delivery_trigger_phrase(form_input: dict, trigger: str) -> str:
    
    t = (trigger or "").strip().lower()
    ru_map = {
        "within_months_from_effective": "с даты вступления договора в силу",
        "within_months_from_signing": "с даты подписания договора",
        "from_order_ack": "с даты подтверждения заказа",
        "from_payment": "с даты поступления оплаты (если применимо)",
    }
    en_map = {
        "within_months_from_effective": "from the Effective Date",
        "within_months_from_signing": "from the signing date",
        "from_order_ack": "from the Order Acknowledgement date",
        "from_payment": "from receipt of payment (if applicable)",
    }
    if _lang(form_input) == "en":
        return en_map.get(t, "from the agreed triggering event")
    return ru_map.get(t, "с даты наступления согласованного события")


def _risk_transfer_phrase(form_input: dict, risk_transfer: str) -> str:
    t = (risk_transfer or "").strip().lower()
    if _lang(form_input) == "en":
        mapping = {
            "upon_delivery": "upon delivery to the Buyer at the delivery point",
            "upon_handover_to_carrier": "upon handover to the carrier",
            "upon_loading": "upon completion of loading",
        }
        return mapping.get(t, "at the agreed moment of handover")
    mapping = {
        "upon_delivery": "в момент передачи товара Покупателю в месте поставки",
        "upon_handover_to_carrier": "в момент передачи товара перевозчику",
        "upon_loading": "по завершении погрузки",
    }
    return mapping.get(t, "в согласованный момент передачи товара")


def _acceptance_doc_phrase(form_input: dict, acceptance_docs: str) -> str:
    d = (acceptance_docs or "").strip().lower()
    if _lang(form_input) == "en":
        if d in ("act", "acceptance_act"):
            return "acceptance act"
        if d in ("invoice",):
            return "invoice"
        if d in ("delivery_note", "waybill"):
            return "delivery note / waybill"
        return "standard delivery/acceptance documents"
    if d in ("act", "acceptance_act"):
        return "акт приемки"
    if d in ("tn", "waybill", "накладная"):
        return "товарная накладная"
    return "стандартные документы поставки (накладная/акт)"

def get_delivery_within_months(form_input: dict) -> int | None:
    d = form_input.get("delivery") or {}
    return d.get("delivery_within_months") or d.get("delivery_term_months") or d.get("delivery_months")


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


def _forbidden_topics(form_input: dict) -> list[str]:
    if _lang(form_input) == "en":
        return [
            "Do NOT mention (these belong to other contract sections):",
            "- Payment terms, penalties/interest for late payment.",
            "- Disputes, court/arbitration, claims procedures.",
            "- General liability/remedies/indemnities.",
            "- Notices as a separate section/mechanism.",
        ]
    return [
        "Запрещено упоминать (это другие секции договора):",
        "- Оплата/расчеты, штрафы/пени/проценты за просрочку оплаты.",
        "- Споры/суд/арбитраж/претензии/претензионный порядок.",
        "- Общая ответственность/убытки/возмещение (liability/remedies).",
        "- Уведомления как отдельный порядок (notices).",
    ]


def _constraints(form_input: dict) -> list[str]:
    if _lang(form_input) == "en":
        return [
            "Do not copy factual details from precedents (addresses, exact dates, Incoterms, company names, clause numbers).",
            "Use only what is provided by the Input Form parameters.",
            "No placeholders like [ADDRESS]/[DATE]/[TERM_months] in the final text.",
            "Avoid repetition: each idea must appear only once.",
            "Do NOT start multiple subclauses with the same opening phrase. Vary wording.",
        ]
    return [
        "Не копируй факты из прецедентов (адреса, точные даты, Incoterms, названия компаний, номера пунктов).",
        "Все условия и переключатели берутся ТОЛЬКО из Input Form.",
        "Не используй плейсхолдеры вида [ADDRESS]/[DATE]/[TERM_months] в финальном тексте.",
        "Не повторяй идеи: каждое утверждение — только один раз.",
        "Не начинай несколько подпунктов одинаковой фразой (например: «Поставщик обязуется…», «Поставка может быть…»). Варьируй формулировки.",
    ]


def _topic_plan(form_input: dict, p: DeliveryTermsParams) -> list[str]:

    months_part_en = (
        f"Delivery term: {p.delivery_term_months} months {_delivery_trigger_phrase(form_input, p.delivery_trigger)}."
        if p.delivery_term_months is not None
        else f"Delivery term: state generically, counting from {_delivery_trigger_phrase(form_input, p.delivery_trigger)} (no numbers)."
    )
    months_part_ru = (
        f"Срок поставки: {p.delivery_term_months} месяцев {_delivery_trigger_phrase(form_input, p.delivery_trigger)}."
        if p.delivery_term_months is not None
        else f"Срок поставки: сформулировать общо, отсчет {_delivery_trigger_phrase(form_input, p.delivery_trigger)} (без чисел)."
    )

    if _lang(form_input) == "en":
        return [
            "Input-Form-dependent rules (must be reflected explicitly; no duplication):",
            f"1) {months_part_en}",
            f"2) Delivery place: {p.delivery_place}.",
            f"3) Partial shipments: {'allowed' if p.partial_deliveries_allowed else 'not allowed'} (strictly per Input Form).",        
            f"4) Risk transfer: {_risk_transfer_phrase(form_input, p.risk_transfer)}.",
            f"5) Delivery/acceptance documents: {_acceptance_doc_phrase(form_input, p.acceptance_docs)} (no requisites).",
            f"6) Packaging: {'required' if p.packaging_required else 'not required'} (if not specified in the form, keep generic).",
            "All other delivery procedures MUST be covered via the Delivery Terms checklist (no new sections; no repetition).",
            "If you need 25–30 items: split procedures into finer-grained steps WITHOUT introducing new contract sections.",
        ]
    return [
        "Разрешённые темы (покрой все; 1 тема = 1 подпункт, без повторов):",
        "Правила, зависящие от Input Form (обязательно отразить явно; без повторов):",
        f"1) {months_part_ru}",
        f"2) Место поставки: {p.delivery_place}.",
        f"3) Частичные поставки: {'разрешены' if p.partial_deliveries_allowed else 'не допускаются'} (строго по форме).",
        f"4) Переход рисков: {_risk_transfer_phrase(form_input, p.risk_transfer)}.",
        f"5) Документы поставки/приемки: {_acceptance_doc_phrase(form_input, p.acceptance_docs)} (без реквизитов).",
        f"6) Упаковка: {'требуется' if p.packaging_required else 'не требуется'} (если в форме не конкретизировано — формулируй общо).",
        "Все прочие процедуры поставки покрывай через TOPIC CHECKLIST (DELIVERY_TERMS), без добавления новых разделов и без повторов.",
        "Если нужно 25–30 подпунктов: дроби процедуры на шаги, НЕ добавляя новые разделы договора.",
        "Пиши только на русском языке.",
    ]


# ----------------------------
# Prompt builder
# ----------------------------
def build_delivery_terms_prompt(form_input: dict, precedents_clean: List[str]) -> str:
    """
    Bilingual prompt for local LLM: generate Delivery Terms section
    using Input Form parameters + stylistic hints from precedents.
    """
    p = _parse_params(form_input)
    lang = _lang(form_input)
    diversity_block = get_section_checklist("delivery_terms", lang) or ""
    snippets = _pick_snippets(precedents_clean, max_snippets=6)

    party_vocab = _party_vocab(form_input)

    # Parameters as explicit requirements
    if _lang(form_input) == "en":
        requirements = [
            f"- Delivery term: {p.delivery_term_months} months {_delivery_trigger_phrase(form_input, p.delivery_trigger)}.",
            f"- Delivery place: {p.delivery_place}.",
            f"- Partial shipments: {'allowed' if p.partial_deliveries_allowed else 'not allowed'}.",
            f"- Incoterms: {'do not specify (not provided)' if not p.incoterms else p.incoterms}.",
            f"- Risk transfer: {_risk_transfer_phrase(form_input, p.risk_transfer)}.",
            f"- Delivery/acceptance docs: {_acceptance_doc_phrase(form_input, p.acceptance_docs)}.",
            f"- Packaging required: {'yes' if p.packaging_required else 'no'} (if not specified, keep generic).",
        ]
    else:
        requirements = [
            f"- Срок поставки: {p.delivery_term_months} месяцев {_delivery_trigger_phrase(form_input, p.delivery_trigger)}.",
            f"- Место поставки: {p.delivery_place}.",
            f"- Частичные поставки: {'разрешены' if p.partial_deliveries_allowed else 'не допускаются'}.",
            f"- Incoterms: {'не указывать (нет в форме)' if not p.incoterms else p.incoterms}.",
            f"- Переход рисков: {_risk_transfer_phrase(form_input, p.risk_transfer)}.",
            f"- Документы поставки/приемки: {_acceptance_doc_phrase(form_input, p.acceptance_docs)}.",
            f"- Упаковка: {'требуется' if p.packaging_required else 'не требуется'} (если не задано явно — формулируй общо).",
        ]

    mandatory_structure = (
        f"{_T(form_input, 'mandatory')}\n"
        "- The section MUST contain AT LEAST 25 subclauses.\n" 
        "- Each subclause must be on a new line.\n"
        "- Each subclause must be a complete legal sentence.\n"
        "- Do NOT merge multiple conditions into one subclause.\n"
        "- If in doubt, add additional subclauses.\n"
        "- Vary sentence openings. Avoid starting many clauses with the same phrase.\n"
        if _lang(form_input) == "en" else

        f"{_T(form_input, 'mandatory')}\n"
        "- Раздел ДОЛЖЕН содержать НЕ МЕНЕЕ 25 подпунктов.\n"    
        "- Каждый подпункт — с новой строки.\n"
        "- Каждый подпункт — одно законченное юридическое предложение.\n"
        "- НЕЛЬЗЯ объединять несколько условий в один подпункт.\n"
        "- Если сомневаешься, добавь дополнительные подпункты.\n"
        "- Варьируй начало предложений. Избегай повторения одних и тех же фраз, как 'Поставщик несет ответственность...').\n"
        "- Пиши только на русском языке.\n"
    )

    

    
    topic_plan = _topic_plan(form_input, p)
    forbidden_topics = _forbidden_topics(form_input)
    constraints = _constraints(form_input)    

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
