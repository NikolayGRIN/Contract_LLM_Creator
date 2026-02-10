# src/state/state_updater.py
from __future__ import annotations

from typing import Any, Dict

from src.state.contract_state import ContractState
from src.state.fact_extractors import extract_payment_facts, extract_delivery_facts


def update_state_from_section(
    *,
    state: ContractState,
    section_id: str,
    section_text: str,
    form: Dict[str, Any],
) -> ContractState:
    if section_id == "payment_terms":
        facts = extract_payment_facts(section_text)

        payment = form.get("payment") or {}

        # currency
        if not form.get("currency") and state.get("commercial_terms.currency") is None and facts.get("currency"):
            state.set("commercial_terms.currency", facts["currency"])

        # payment_due_days
        if payment.get("payment_due_days") is None and state.get("payment_terms.payment_due_days") is None:
            if facts.get("payment_due_days") is not None:
                state.set("payment_terms.payment_due_days", int(facts["payment_due_days"]))

        # penalty rate
        if not payment.get("late_payment_penalty_rate") and state.get("payment_terms.late_payment_penalty_rate") is None:
            if facts.get("late_payment_penalty_rate"):
                state.set("payment_terms.late_payment_penalty_rate", facts["late_payment_penalty_rate"])

    elif section_id == "delivery_terms":
        facts = extract_delivery_facts(section_text)

        delivery = form.get("delivery") or {}

        if not delivery.get("incoterms") and state.get("delivery_terms.incoterms") is None and facts.get("incoterms"):
            state.set("delivery_terms.incoterms", facts["incoterms"])

        if delivery.get("delivery_days") is None and state.get("delivery_terms.delivery_days") is None:
            if facts.get("delivery_days") is not None:
                state.set("delivery_terms.delivery_days", int(facts["delivery_days"]))

        if not delivery.get("delivery_place") and state.get("delivery_terms.delivery_place") is None and facts.get("delivery_place"):
            state.set("delivery_terms.delivery_place", facts["delivery_place"])

    return state
