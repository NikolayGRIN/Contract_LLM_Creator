# src/prompts/consistency_context.py
from __future__ import annotations

from typing import List

from src.state.contract_state import ContractState


def build_consistency_context(*, state: ContractState, target_section_id: str) -> str:
   
    lang = (state.get("meta.language_mode") or "ru").lower()
    # party labels
    seller_en = state.get("parties.seller.role_label_en", "Seller")
    buyer_en = state.get("parties.buyer.role_label_en", "Buyer")
    seller_ru = state.get("parties.seller.role_label_ru", "Продавец")
    buyer_ru = state.get("parties.buyer.role_label_ru", "Покупатель")

    # commercial
    currency = state.get("commercial_terms.currency")
    contract_price = state.get("commercial_terms.contract_price")
    vat_mode = state.get("commercial_terms.vat_mode")

    # payment
    payment_due_days = state.get("payment_terms.payment_due_days")
    payment_trigger = state.get("payment_terms.payment_trigger")
    prepayment_required = state.get("payment_terms.prepayment_required")
    late_penalty_enabled = state.get("payment_terms.late_payment_penalty_enabled")
    late_penalty_rate = state.get("payment_terms.late_payment_penalty_rate")

    # delivery
    delivery_days = state.get("delivery_terms.delivery_days")
    delivery_place = state.get("delivery_terms.delivery_place")
    partial_shipments_allowed = state.get("delivery_terms.partial_shipments_allowed")
    incoterms = state.get("delivery_terms.incoterms")
    incoterms_version = state.get("delivery_terms.incoterms_version")

    # acceptance
    acceptance_required = state.get("acceptance.acceptance_required")
    acceptance_period_days = state.get("acceptance.acceptance_period_days")
    acceptance_document = state.get("acceptance.acceptance_document")

    # warranties
    warranty_months = state.get("warranties.warranty_period_months")
    warranty_start = state.get("warranties.warranty_start")
    warranty_remedy = state.get("warranties.remedy")

    # liability (кратко)
    cap_enabled = state.get("liability_terms.liability_cap_enabled")
    cap_type = state.get("liability_terms.liability_cap_type")
    indirect_excluded = state.get("liability_terms.indirect_damages_excluded")

    facts: List[str] = []

    if lang == "ru":
        facts.append(f"- Обозначения сторон: используйте '{seller_ru}' и '{buyer_ru}' последовательно.")
        if currency: facts.append(f"- Валюта: {currency}.")
        if contract_price is not None: facts.append(f"- Цена договора: {contract_price}.")
        if vat_mode: facts.append(f"- Режим НДС: {vat_mode}.")

        if payment_due_days is not None: facts.append(f"- Срок оплаты: {payment_due_days} календарных дней.")
        if payment_trigger: facts.append(f"- Триггер оплаты: {payment_trigger}.")
        if prepayment_required is not None: facts.append(f"- Предоплата: {bool(prepayment_required)}.")
        if late_penalty_enabled is not None: facts.append(f"- Неустойка за просрочку оплаты: {bool(late_penalty_enabled)}.")
        if late_penalty_rate: facts.append(f"- Ставка неустойки (если применяется): {late_penalty_rate}.")

        if delivery_days is not None: facts.append(f"- Срок поставки: {delivery_days} календарных дней.")
        if delivery_place: facts.append(f"- Место поставки: {delivery_place}.")
        if partial_shipments_allowed is not None: facts.append(f"- Частичные отгрузки: {bool(partial_shipments_allowed)}.")
        if incoterms:
            v = f" {incoterms_version}" if incoterms_version else ""
            facts.append(f"- Инкотермс: {incoterms}{v}.")

        if acceptance_required is not None: facts.append(f"- Приёмка требуется: {bool(acceptance_required)}.")
        if acceptance_period_days is not None: facts.append(f"- Срок приёмки: {acceptance_period_days} дней.")
        if acceptance_document: facts.append(f"- Документ приёмки: {acceptance_document}.")

        if warranty_months is not None: facts.append(f"- Гарантия: {warranty_months} месяцев.")
        if warranty_start: facts.append(f"- Начало гарантии: {warranty_start}.")
        if warranty_remedy: facts.append(f"- Способ устранения дефектов: {warranty_remedy}.")

        if cap_enabled is not None: facts.append(f"- Лимит ответственности включён: {bool(cap_enabled)}.")
        if cap_type: facts.append(f"- Тип лимита ответственности: {cap_type}.")
        if indirect_excluded is not None: facts.append(f"- Косвенные убытки исключены: {bool(indirect_excluded)}.")

        header = "ТРЕБОВАНИЯ СОГЛАСОВАННОСТИ (ОБЯЗАТЕЛЬНО)\n"
        footer = (
            "\nСТРОГИЕ ПРАВИЛА:\n"
            "1) Не противоречьте фактам выше.\n"
            "2) Если факт отсутствует — не придумывайте конкретное значение; пишите обобщённо.\n"
            "3) Всегда используйте одинаковые обозначения сторон.\n"
        )
    else:
        facts.append(f"- Parties labels: use '{seller_en}' and '{buyer_en}' consistently.")
        if currency: facts.append(f"- Currency: {currency}.")
        if contract_price is not None: facts.append(f"- Contract price: {contract_price}.")
        if vat_mode: facts.append(f"- VAT mode: {vat_mode}.")

        if payment_due_days is not None: facts.append(f"- Payment term: {payment_due_days} calendar days.")
        if payment_trigger: facts.append(f"- Payment trigger: {payment_trigger}.")
        if prepayment_required is not None: facts.append(f"- Prepayment required: {bool(prepayment_required)}.")
        if late_penalty_enabled is not None: facts.append(f"- Late payment penalty enabled: {bool(late_penalty_enabled)}.")
        if late_penalty_rate: facts.append(f"- Late payment penalty rate (if applicable): {late_penalty_rate}.")

        if delivery_days is not None: facts.append(f"- Delivery time: {delivery_days} calendar days.")
        if delivery_place: facts.append(f"- Delivery place: {delivery_place}.")
        if partial_shipments_allowed is not None: facts.append(f"- Partial shipments allowed: {bool(partial_shipments_allowed)}.")
        if incoterms:
            v = f" {incoterms_version}" if incoterms_version else ""
            facts.append(f"- Incoterms: {incoterms}{v}.")

        if acceptance_required is not None: facts.append(f"- Acceptance required: {bool(acceptance_required)}.")
        if acceptance_period_days is not None: facts.append(f"- Acceptance period: {acceptance_period_days} days.")
        if acceptance_document: facts.append(f"- Acceptance document: {acceptance_document}.")

        if warranty_months is not None: facts.append(f"- Warranty: {warranty_months} months.")
        if warranty_start: facts.append(f"- Warranty starts from: {warranty_start}.")
        if warranty_remedy: facts.append(f"- Warranty remedy: {warranty_remedy}.")

        if cap_enabled is not None: facts.append(f"- Liability cap enabled: {bool(cap_enabled)}.")
        if cap_type: facts.append(f"- Liability cap type: {cap_type}.")
        if indirect_excluded is not None: facts.append(f"- Indirect damages excluded: {bool(indirect_excluded)}.")

        header = "CONSISTENCY REQUIREMENTS (MUST FOLLOW)\n"
        footer = (
            "\nSTRICT RULES:\n"
            "1) Do NOT contradict any fact above.\n"
            "2) If a fact is missing, do NOT invent a specific value; keep it generic.\n"
            "3) Use the same party labels everywhere.\n"
        )

    body = "\n".join(facts) if facts else ("- No fixed facts yet." if lang == "en" else "- Пока нет зафиксированных фактов.")
    return header + body + footer
