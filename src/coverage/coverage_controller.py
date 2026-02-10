# src/coverage/coverage_controller.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from src.planning.contract_planner import ContractPlan, SectionSpec


# ----------------------------
# Result models
# ----------------------------
@dataclass(frozen=True)
class CoverageReport:
    required_total: int
    present_required: int
    missing_required: List[str]
    present_optional: List[str]
    unknown_present: List[str]
    completion_ratio: float
    notes: List[str]


@dataclass(frozen=True)
class PrecheckResult:
    to_generate: List[str]
    notes: List[str]


# ----------------------------
# required_if evaluation (safe-ish, minimal)
# ----------------------------
def _safe_eval_required_if(expr: str, form: Dict[str, Any]) -> bool:
    """
    Very small expression evaluator:
      - "path == true/false/null/none/'str'/\"str\""
      - "path != null/none/'str'/\"str\""
    path is read from form via dotted access: e.g. "payment.prepayment_required"
    """
    e = (expr or "").strip()
    if not e:
        return False

    def _get_path(path: str) -> Any:
        cur: Any = form
        for part in path.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return None
            cur = cur[part]
        return cur

    low = e.lower()

    if "==" in low:
        left, right = [x.strip() for x in e.split("==", 1)]
        rv = right.strip().strip('"').strip("'")
        lv = _get_path(left)

        if rv.lower() in ("true", "false"):
            return bool(lv) is (rv.lower() == "true")
        if rv.lower() in ("null", "none"):
            return lv is None
        return str(lv or "").strip().lower() == rv.lower()

    if "!=" in low:
        left, right = [x.strip() for x in e.split("!=", 1)]
        rv = right.strip().strip('"').strip("'")
        lv = _get_path(left)

        if rv.lower() in ("null", "none"):
            return lv is not None
        return str(lv or "").strip().lower() != rv.lower()

    return False


def _is_required(spec: SectionSpec, form: Dict[str, Any], notes: List[str]) -> bool:
    if getattr(spec, "required_if", None):
        try:
            return _safe_eval_required_if(spec.required_if, form)
        except Exception as ex:
            notes.append(f"required_if eval failed for {spec.section_id}: {ex}")
            return bool(getattr(spec, "required", True))
    return bool(getattr(spec, "required", True))


# ----------------------------
# Pre-check: decide what to generate now
# ----------------------------
def precheck_missing_sections(
    plan: ContractPlan,
    *,
    already_generated: Set[str],
    form: Dict[str, Any],
) -> PrecheckResult:
    """
    Returns:
      - to_generate: section_ids (in plan order) that are required and not already generated
      - notes: diagnostics (unknown ids, required_if eval errors, etc.)
    """
    notes: List[str] = []
    ordered = list(plan.ordered_section_ids())
    spec_by_id = {s.section_id: s for s in plan.sections}

    missing: List[str] = []
    for sid in ordered:
        spec = spec_by_id.get(sid)
        if spec is None:
            notes.append(f"Unknown section_id in plan.order: {sid}")
            continue

        if _is_required(spec, form, notes) and sid not in already_generated:
            missing.append(sid)

    return PrecheckResult(to_generate=missing, notes=notes)


# ----------------------------
# Post-check: coverage report based on actually generated section_ids
# ----------------------------
def postcheck_coverage(
    plan: ContractPlan,
    *,
    generated_sections: Set[str],
    form: Dict[str, Any],
) -> CoverageReport:
    notes: List[str] = []
    spec_by_id = {s.section_id: s for s in plan.sections}

    required_ids: List[str] = []
    optional_ids: List[str] = []

    for spec in plan.sections:
        if _is_required(spec, form, notes):
            required_ids.append(spec.section_id)
        else:
            optional_ids.append(spec.section_id)

    missing_required = [sid for sid in required_ids if sid not in generated_sections]
    present_required = [sid for sid in required_ids if sid in generated_sections]
    present_optional = [sid for sid in optional_ids if sid in generated_sections]
    unknown_present = sorted([sid for sid in generated_sections if sid not in spec_by_id])

    required_total = len(required_ids)
    present_required_n = len(present_required)
    completion_ratio = (present_required_n / required_total) if required_total else 1.0

    if missing_required:
        notes.append(f"Missing required sections: {missing_required}")
    if unknown_present:
        notes.append(f"Unknown generated sections (not in plan.sections): {unknown_present}")

    return CoverageReport(
        required_total=required_total,
        present_required=present_required_n,
        missing_required=missing_required,
        present_optional=present_optional,
        unknown_present=unknown_present,
        completion_ratio=completion_ratio,
        notes=notes,
    )
