from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from prompts.consistency_context import build_consistency_context
from state.contract_state import ContractState


# =========================================================
# Config
# =========================================================

@dataclass(frozen=True)
class PromptBuildConfig:
    templates_dir: Path
    max_precedents: int = 5
    max_chars_per_precedent: int = 1800
    include_precedents: bool = True
    allow_fallback_template: bool = True
    include_state_facts: bool = True   # ⭐ NEW


# =========================================================
# Template loading
# =========================================================

def _template_path(templates_dir: Path, section_id: str) -> Path:
    return templates_dir / f"{section_id}.txt"


def load_section_template(
    *,
    templates_dir: Path,
    section_id: str,
    allow_fallback: bool = True,
) -> str:

    path = _template_path(templates_dir, section_id)

    if path.exists():
        return path.read_text(encoding="utf-8")

    if not allow_fallback:
        raise FileNotFoundError(f"Template not found: {path}")

    return (
        "STRICT SECTION TEMPLATE (FALLBACK)\n"
        "Generate professional contract clauses for section: {section_id}\n\n"
        "Follow the facts below strictly.\n"
        "Return ONLY the section text.\n"
    )


# =========================================================
# -------- NEW: STATE FACTS BLOCK --------------------------
# =========================================================

SECTION_FACTS_MAP = {

    "payment_terms": [
        ("Currency", "commercial_terms.currency"),
        ("Contract price", "commercial_terms.contract_price"),
        ("Payment days", "payment_terms.payment_due_days"),
        ("Payment trigger", "payment_terms.payment_trigger"),
        ("Prepayment required", "payment_terms.prepayment_required"),
        ("Withholding allowed", "payment_terms.withholding_allowed"),
        ("Suspension right", "payment_terms.suspension_right"),
        ("Bank charges", "payment_terms.bank_charges"),
        ("Late penalty enabled", "payment_terms.late_payment_penalty_enabled"),
        ("Late penalty rate", "payment_terms.late_payment_penalty_rate"),
    ],

    "delivery_terms": [
        ("Delivery days", "delivery_terms.delivery_days"),
        ("Delivery place", "delivery_terms.delivery_place"),
        ("Partial shipments allowed", "delivery_terms.partial_shipments_allowed"),
        ("Incoterms", "delivery_terms.incoterms"),
    ],

    "acceptance": [
        ("Acceptance required", "acceptance.acceptance_required"),
        ("Acceptance period days", "acceptance.acceptance_period_days"),
        ("Acceptance document", "acceptance.acceptance_document"),
    ],

    "warranties": [
        ("Warranty months", "warranties.warranty_period_months"),
        ("Warranty start", "warranties.warranty_start"),
        ("Remedy", "warranties.remedy"),
    ],

    "liability_terms": [
        ("Liability cap enabled", "liability_terms.liability_cap_enabled"),
        ("Liability cap type", "liability_terms.liability_cap_type"),
        ("Indirect damages excluded", "liability_terms.indirect_damages_excluded"),
        ("Delay penalty enabled", "liability_terms.delay_in_delivery_penalty_enabled"),
    ],

    "legal_terms": [
        ("Governing law", "legal_terms.governing_law"),
        ("Dispute resolution", "legal_terms.dispute_resolution"),
        ("Court place", "legal_terms.court_place"),
    ],
}


def _lang(state: ContractState) -> str:
    return state.get("meta.language_mode", "ru")


def _fmt(v):
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "yes" if v else "no"
    return str(v)


def build_state_facts_block(state: ContractState, section_id: str) -> str:
    """
    ⭐ NEW: inject structured facts directly from ContractState
    This dramatically improves generation quality.
    """

    pairs = SECTION_FACTS_MAP.get(section_id)
    if not pairs:
        return ""

    lang = _lang(state)

    lines: List[str] = []

    for label, path in pairs:
        value = state.get(path)
        if value is not None:
            lines.append(f"- {label}: {_fmt(value)}.")

    if not lines:
        return ""

    if lang == "en":
        header = "\nFACTS FROM FORM (MUST FOLLOW STRICTLY):\n"
    else:
        header = "\nФАКТЫ ИЗ ФОРМЫ (СТРОГО СОБЛЮДАТЬ):\n"

    return header + "\n".join(lines)


# =========================================================
# Precedents block
# =========================================================

def _truncate(text: str, max_chars: int) -> str:
    return text[:max_chars] if len(text) <= max_chars else text[:max_chars] + "..."


def build_precedents_block(
    precedents: List[str],
    *,
    max_precedents: int,
    max_chars_per_precedent: int,
    language_mode: str,
) -> str:

    if not precedents:
        return ""

    items = [
        f"[PRECEDENT {i+1}]\n{_truncate(p, max_chars_per_precedent)}"
        for i, p in enumerate(precedents[:max_precedents])
    ]

    if language_mode == "en":
        header = "\nSTYLE HINTS ONLY (do NOT copy facts):\n"
    else:
        header = "\nПРЕЦЕДЕНТЫ ТОЛЬКО ДЛЯ СТИЛЯ:\n"

    return header + "\n\n".join(items)


# =========================================================
# Public API
# =========================================================

def build_section_prompt(
    *,
    section_id: str,
    form: Dict[str, Any],
    state: ContractState,
    precedents: Optional[List[str]],
    cfg: PromptBuildConfig,
) -> str:

    language_mode = state.get("meta.language_mode", "ru")

    # 1️⃣ Consistency
    consistency_block = build_consistency_context(state=state, target_section_id=section_id)

    # 2️⃣ Template
    tpl = load_section_template(
        templates_dir=cfg.templates_dir,
        section_id=section_id,
        allow_fallback=cfg.allow_fallback_template,
    )

    strict_block = tpl.replace("{section_id}", section_id)

    # 3️⃣ ⭐ NEW: state facts
    facts_block = ""
    if cfg.include_state_facts:
        facts_block = build_state_facts_block(state, section_id)

    # 4️⃣ Precedents
    prec_block = ""
    if cfg.include_precedents and precedents:
        prec_block = build_precedents_block(
            precedents,
            max_precedents=cfg.max_precedents,
            max_chars_per_precedent=cfg.max_chars_per_precedent,
            language_mode=language_mode,
        )

    prompt = (
        consistency_block.strip()
        + "\n\n"
        + facts_block
        + "\n\n"
        + strict_block.strip()
        + prec_block
        + "\n"
    )

    return prompt


def default_prompt_config() -> PromptBuildConfig:
    here = Path(__file__).resolve()
    templates_dir = here.parent / "templates"
    return PromptBuildConfig(templates_dir=templates_dir)
