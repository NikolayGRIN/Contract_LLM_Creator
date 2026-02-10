# src/planning/contract_planner.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Literal


LanguageMode = Literal["ru", "en"]
ContractType = Literal["supply"]


@dataclass(frozen=True)
class SectionSpec:
    section_id: str
    required: bool = True
    required_if: Optional[str] = None
    title: Optional[str] = None


@dataclass(frozen=True)
class ContractPlan:
    contract_type: ContractType
    language_mode: LanguageMode
    sections: List[SectionSpec]
    order: List[str] = field(default_factory=list)
    generation_policy: Dict[str, Any] = field(default_factory=dict)

    def ordered_section_ids(self) -> List[str]:
        ids = [s.section_id for s in self.sections]
        if not self.order:
            return ids
        out: List[str] = []
        seen = set()
        for sid in self.order:
            if sid in ids and sid not in seen:
                out.append(sid)
                seen.add(sid)
        for sid in ids:
            if sid not in seen:
                out.append(sid)
        return out


SUPPLY_CONTRACT_V1_SECTIONS: List[SectionSpec] = [
    SectionSpec("definitions", required=True, title="Definitions"),
    SectionSpec("subject_of_contract", required=True, title="Subject of Contract"),
    SectionSpec("price_and_taxes", required=True, title="Price and Taxes"),
    SectionSpec("payment_terms", required=True, title="Payment Terms"),
    SectionSpec("delivery_terms", required=True, title="Delivery Terms"),
    SectionSpec("acceptance_and_inspection", required=True, title="Acceptance & Inspection"),
    SectionSpec("warranties", required=True, title="Warranties / Quality"),
    SectionSpec("liability_and_penalties", required=True, title="Liability & Penalties"),
    SectionSpec("force_majeure", required=True, title="Force Majeure"),
    SectionSpec("governing_law_and_disputes", required=True, title="Governing Law & Disputes"),
]


def build_contract_plan(form: Dict[str, Any]) -> ContractPlan:
    contract_type: ContractType = form.get("contract_type", "supply")
    language_mode_raw = str(form.get("language_mode", "en")).strip().lower()

    if contract_type != "supply":
        raise ValueError(f"Unsupported contract_type={contract_type!r}")

    language_mode: LanguageMode = "en"  # default
    if language_mode_raw in ("ru", "en"):
        language_mode = language_mode_raw  # type: ignore

    order = [
        "definitions",
        "subject_of_contract",
        "price_and_taxes",
        "payment_terms",
        "delivery_terms",
        "acceptance_and_inspection",
        "warranties",
        "liability_and_penalties",
        "force_majeure",
        "governing_law_and_disputes",
    ]

    generation_policy: Dict[str, Any] = {
        "top_k": int(form.get("top_k", 7)),
        "max_attempts": int(form.get("max_attempts", 3)),

        # ✅ сейчас retrieval только для 2 секций
        "retrieval_enabled_now": {
            "payment_terms": True,
            "delivery_terms": True,
        },

        # ✅ “слоты под будущее”: пока form-based, но архитектурно помечены
        "retrieval_fallback_later": {
            "acceptance_and_inspection": True,
            "liability_and_penalties": True,
        },
    }

    return ContractPlan(
        contract_type=contract_type,
        language_mode=language_mode,
        sections=list(SUPPLY_CONTRACT_V1_SECTIONS),
        order=order,
        generation_policy=generation_policy,
    )
