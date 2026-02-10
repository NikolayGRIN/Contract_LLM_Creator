# src/generation/acceptance_generate.py
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


# ----------------------------
# Helpers
# ----------------------------
def _lang(form_input: dict) -> str:
    return str((form_input or {}).get("language_mode", "ru")).strip().lower()


def _safe_get(d: Dict[str, Any], path: str, default=None):
    cur: Any = d
    for key in path.split("."):
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def _norm_spaces(s: str) -> str:
    s = (s or "").replace("\u00A0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


# ----------------------------
# Facts extraction
# ----------------------------
@dataclass
class AcceptanceFacts:
    acceptance_required: Optional[bool]
    acceptance_period_days: Optional[int]
    acceptance_document: Optional[str]
    acceptance_rules: Optional[str]
    documents_required: Optional[list]

    inspection_scope: Optional[str]
    defect_notice_method: Optional[str]
    silent_acceptance_rule: Optional[str]
    remedy_options: Optional[list]
    remedy_time_days: Optional[int]


def extract_acceptance_facts(form_input: Dict[str, Any]) -> AcceptanceFacts:
    acc = _safe_get(form_input, "acceptance", {}) or {}
    details = (acc.get("acceptance_details") or {}) if isinstance(acc, dict) else {}

    def _as_list(v):
        if v is None:
            return None
        if isinstance(v, list):
            return [str(x) for x in v if str(x).strip()]
        if isinstance(v, str) and v.strip():
            return [v.strip()]
        return None

    return AcceptanceFacts(
        acceptance_required=acc.get("acceptance_required"),
        acceptance_period_days=acc.get("acceptance_period_days"),
        acceptance_document=acc.get("acceptance_document"),
        acceptance_rules=acc.get("acceptance_rules"),
        documents_required=_as_list(acc.get("documents_required")),

        inspection_scope=details.get("inspection_scope"),
        defect_notice_method=details.get("defect_notice_method"),
        silent_acceptance_rule=details.get("silent_acceptance_rule"),
        remedy_options=_as_list(details.get("remedy_options")),
        remedy_time_days=details.get("remedy_time_days"),
    )


def _facts_block_ru(f: AcceptanceFacts) -> str:
    lines = []

    def add(k: str, v: Any):
        if v is None or v == "" or v == []:
            return
        lines.append(f"- {k}: {v}")

    add("acceptance_required", f.acceptance_required)
    add("acceptance_period_days", f.acceptance_period_days)
    add("acceptance_document", f.acceptance_document)
    add("acceptance_rules", f.acceptance_rules)
    add("documents_required", f.documents_required)
    add("inspection_scope", f.inspection_scope)
    add("defect_notice_method", f.defect_notice_method)
    add("silent_acceptance_rule", f.silent_acceptance_rule)
    add("remedy_options", f.remedy_options)
    add("remedy_time_days", f.remedy_time_days)

    return "\n".join(lines) if lines else "- (нет специальных фактов в форме)"


def _facts_block_en(f: AcceptanceFacts) -> str:
    lines = []

    def add(k: str, v: Any):
        if v is None or v == "" or v == []:
            return
        lines.append(f"- {k}: {v}")

    add("acceptance_required", f.acceptance_required)
    add("acceptance_period_days", f.acceptance_period_days)
    add("acceptance_document", f.acceptance_document)
    add("acceptance_rules", f.acceptance_rules)
    add("documents_required", f.documents_required)
    add("inspection_scope", f.inspection_scope)
    add("defect_notice_method", f.defect_notice_method)
    add("silent_acceptance_rule", f.silent_acceptance_rule)
    add("remedy_options", f.remedy_options)
    add("remedy_time_days", f.remedy_time_days)

    return "\n".join(lines) if lines else "- (no specific facts in the form)"


# ----------------------------
# Prompt builder (facts + precedents)
# ----------------------------
def build_acceptance_prompt(form_input: dict, precedents_clean: Optional[List[str]] = None) -> str:
    """
    Build prompt for section "ACCEPTANCE AND INSPECTION" using:
      - facts from Input Form
      - precedent snippets (style hints) from embeddings retrieval
    NOTE: numbering will be added later by run_generate.py, so here we forbid numbering.
    """
    precedents_clean = precedents_clean or []
    lang = _lang(form_input)
    f = extract_acceptance_facts(form_input)

    # compact precedents block
    ex_lines: List[str] = []
    for i, txt in enumerate(precedents_clean[:6], start=1):
        t = (txt or "").strip()
        if not t:
            continue
        ex_lines.append(f"[EX{i}] {t}")
    precedents_block = "\n\n".join(ex_lines) if ex_lines else ("- (нет прецедентов)" if lang == "ru" else "- (no precedents)")

    if lang == "ru":
        return _norm_spaces(
            f"""
Ты — юрист по международным договорам поставки оборудования. Сгенерируй раздел договора «ПРИЕМКА И ИНСПЕКЦИЯ».

ОБЯЗАТЕЛЬНЫЕ ТРЕБОВАНИЯ:
- Нумерацию НЕ ставь (ни «6.1», ни «1.»). Нумерацию добавит система.
- НЕ выводи заголовок раздела отдельной строкой.
- Каждая строка = одно законченное юридическое предложение.
- Без пустых строк, без markdown, без маркеров, без списков с bullets.
- Не придумывай адреса, номера документов, реквизиты, даты и значения, которых нет в FACTS.
- Если acceptance_required=false: не делай акт/сертификат обязательным условием для приемки; опиши упрощенную приемку.

Нужно покрыть (без повторов):
- документы приемки/поставки (в общем виде),
- порядок осмотра при поставке,
- сроки приемки (если заданы),
- порядок уведомления о дефектах/несоответствиях,
- правило “молчаливой приемки” (если задано),
- способы устранения/ремедии и сроки (если заданы),
- последствия выявления дефектов и оформление замечаний.

FACTS (используй, если заданы):
{_facts_block_ru(f)}

PRECEDENTS (стиль/формулировки, НЕ копировать дословно):
{precedents_block}

Выведи ТОЛЬКО текст раздела.
"""
        )

    # EN
    return _norm_spaces(
        f"""
You are a lawyer drafting an international equipment supply contract. Generate the section “ACCEPTANCE AND INSPECTION”.

MANDATORY REQUIREMENTS:
- Do NOT add any numbering (no “6.1”, no “1.”). The system will add numbering.
- Do NOT output the section title as a separate line.
- Each line must be exactly ONE complete legal sentence.
- No blank lines, no markdown, no bullets.
- Do not invent addresses, document numbers, dates, or factual values not present in FACTS.
- If acceptance_required=false: keep acceptance lightweight and do not make an acceptance act mandatory.

Cover (no repetition):
- delivery/acceptance documents (generic),
- inspection upon delivery,
- acceptance timeline (if provided),
- discrepancy/defect notice procedure,
- silent acceptance rule (if provided),
- remedies and remedy timeline (if provided),
- consequences of defects and documentation of remarks.

FACTS (use if provided):
{_facts_block_en(f)}

PRECEDENTS (style only, do NOT copy verbatim):
{precedents_block}

Output ONLY the section text.
"""
    )
