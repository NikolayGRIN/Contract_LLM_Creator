from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

from docx import Document


# -----------------------------
# IO
# -----------------------------
def read_docx_text(docx_path: Path) -> str:
    """Read .docx and return plain text (paragraphs joined by newline)."""
    doc = Document(str(docx_path))
    parts: List[str] = []
    for p in doc.paragraphs:
        t = (p.text or "").strip()
        if t:
            parts.append(t)
    return "\n".join(parts)


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


# -----------------------------
# Sections
# -----------------------------
_TOP_HEADING_RE = re.compile(r"^\s*(\d+)\.\s+.+$")


def split_into_top_sections(text: str) -> Dict[int, str]:
    """
    Split contract text by top-level headings like '1. ОПРЕДЕЛЕНИЯ'.
    Returns mapping {section_number: section_text_including_heading}.
    """
    lines = text.splitlines()
    indices: List[Tuple[int, int]] = []
    for i, line in enumerate(lines):
        m = _TOP_HEADING_RE.match(line)
        if m:
            indices.append((int(m.group(1)), i))

    sections: Dict[int, str] = {}
    for idx, (sec_no, start) in enumerate(indices):
        end = indices[idx + 1][1] if idx + 1 < len(indices) else len(lines)
        sections[sec_no] = "\n".join(lines[start:end]).strip()
    return sections


# -----------------------------
# Metrics
# -----------------------------
def metric_coverage(sections: Dict[int, str], expected_sections: int = 10) -> float:
    expected = set(range(1, expected_sections + 1))
    present = set(sections.keys())
    return len(expected & present) / len(expected)


def metric_numbering_valid(sections: Dict[int, str]) -> Tuple[bool, Dict[str, Any]]:
    """
    Validates:
    - top level: 1..N without gaps (N = max present)
    - subclauses inside each section: X.1, X.2, ... without gaps/duplicates
    """
    nums = sorted(sections.keys())
    if not nums:
        return False, {"top_valid": False, "issues": [("all", "no_sections")]}

    top_valid = nums == list(range(1, max(nums) + 1))
    issues: List[Tuple[int, str]] = []

    sub_ok = True
    for sec, txt in sections.items():
        subs: List[int] = []
        for line in txt.splitlines():
            m = re.match(rf"^\s*{sec}\.(\d+)\.\s+", line)
            if m:
                subs.append(int(m.group(1)))
        if not subs:
            continue
        if len(subs) != len(set(subs)):
            sub_ok = False
            issues.append((sec, "duplicate_subclause_numbers"))
        if sorted(subs) != list(range(1, max(subs) + 1)):
            sub_ok = False
            issues.append((sec, "gap_or_nonsequential_subclause_numbers"))

    return bool(top_valid and sub_ok), {"top_valid": top_valid, "issues": issues}


def metric_section_size_ok(
    sections: Dict[int, str],
    min_chars_no_spaces: int = 700,
) -> Tuple[bool, Dict[int, int]]:
    sizes: Dict[int, int] = {}
    ok = True
    for sec, txt in sections.items():
        sz = len(re.sub(r"\s+", "", txt))
        sizes[sec] = sz
        if sz < min_chars_no_spaces:
            ok = False
    return ok, sizes


def metric_repetition_ratio(text: str, min_word_len: int = 4) -> float:
    """
    Type-token ratio for words length >= min_word_len.
    (Less sensitive to 'и/в/по/что' in legal text.)
    """
    tokens = re.findall(r"[A-Za-zА-Яа-яЁё]+", text.lower())
    tokens = [t for t in tokens if len(t) >= min_word_len]
    if not tokens:
        return 1.0
    return len(set(tokens)) / len(tokens)


def metric_duplicate_sentences(text: str, min_len: int = 20) -> Tuple[int, Dict[str, int]]:
    """
    Counts exact duplicate sentences after normalization:
    - remove numbering prefix like '5.12.'
    - lowercase, collapse whitespace
    """
    t = text.replace("\n", " ")
    raw_sents = re.split(r"(?<=[.!?])\s+", t)
    norm: List[str] = []
    for s in raw_sents:
        s = s.strip()
        if not s:
            continue
        s = re.sub(r"^\s*\d+(\.\d+)*\.\s*", "", s)
        s = re.sub(r"\s+", " ", s).lower()
        if len(s) >= min_len:
            norm.append(s)

    from collections import Counter
    c = Counter(norm)
    dups = {sent: n for sent, n in c.items() if n > 1}
    dup_count = sum(n - 1 for n in dups.values())
    return dup_count, dups


# -----------------------------
# Form-driven checks (strict-ish)
# -----------------------------
def _digits(s: Any) -> str:
    return re.sub(r"\D", "", str(s))


@dataclass(frozen=True)
class PresenceResult:
    score: float
    matched: List[str]
    missing: List[str]


def metric_parameter_presence(text: str, form: Dict[str, Any]) -> PresenceResult:
    """
    Checks a compact 'critical' set of parameters from the Input Form.
    Score = matched / total_required.
    """
    text_lc = text.lower()

    required: List[Tuple[str, bool]] = []

    # стало (устойчиво к падежам/множественному числу):
    gd = str(form["goods"]["goods_description"]).lower()
    gd_tokens = re.findall(r"[a-zа-яё]+", gd)
    has_chpu = "чпу" in text_lc
    has_stank_root = re.search(r"\bстанк", text_lc) is not None  
    if ("чпу" in gd_tokens) and any(t.startswith("стан") for t in gd_tokens):
        ok_goods = has_chpu and has_stank_root
    else:
        ok_goods = all(t in text_lc for t in gd_tokens)
    required.append(("goods_description", ok_goods))

    # price / currency
    required.append(("currency", str(form["commercial"]["currency"]).lower() in text_lc))
    required.append(("contract_price", _digits(form["commercial"]["contract_price"]) in _digits(text)))

    # payment
    required.append(("payment_term_days", re.search(rf"\b{form['payment']['payment_term_days']}\b", text) is not None))
    required.append(("prepayment_percent", (f"{form['payment']['prepayment_percent']}%" in text) or ("предоплат" in text_lc and re.search(rf"\b{form['payment']['prepayment_percent']}\b", text) is not None)))

    # delivery
    required.append(("delivery_place", str(form["delivery"]["delivery_place"]).lower() in text_lc))
    required.append(("delivery_within_months", (re.search(rf"\b{form['delivery']['delivery_within_months']}\b", text) is not None) and ("месяц" in text_lc)))
    required.append(("incoterms_and_version", (str(form["delivery"]["incoterms"]).lower() in text_lc) and (str(form["delivery"]["incoterms_version"]) in text)))

    # acceptance
    required.append(("acceptance_period_days", (re.search(rf"\b{form['acceptance']['acceptance_period_days']}\b", text) is not None) and ("приемк" in text_lc)))

    # warranties
    required.append(("warranty_period_months", (re.search(rf"\b{form['warranties']['warranty_period_months']}\b", text) is not None) and ("гарант" in text_lc)))

    matched = [name for name, ok in required if ok]
    missing = [name for name, ok in required if not ok]
    score = len(matched) / len(required) if required else 1.0
    return PresenceResult(score=score, matched=matched, missing=missing)


def metric_hallucination_count(text: str, form: Dict[str, Any]) -> Tuple[int, List[str]]:
    """
    Counts contradictions to the Input Form for a few high-impact fields.    
    """
    issues: List[str] = []
    text_lc = text.lower()

    # Governing law: require explicit mention of the exact phrase if provided.
    gov = str(form["legal"]["governing_law"]).lower().strip()
    if gov and gov not in text_lc:
        issues.append("governing_law_mismatch_or_missing")

    # Liability: the form says RF (in general_rule); flag if text mentions USA law.
    general_rule = str(form["liability"]["liability_details"]["general_rule"]).lower()
    if "рф" in general_rule and "законодательством сша" in text_lc:
        issues.append("liability_law_mismatch_usa")

    return len(issues), issues


# -----------------------------
# Runner
# -----------------------------
@dataclass
class Metrics:
    coverage: float
    numbering_valid: bool
    section_size_ok: bool
    repetition_ratio: float
    duplicate_sentences: int
    parameter_presence: float
    hallucination_count: int
    details: Dict[str, Any]


def evaluate(
    contract_docx: Path,
    form_json: Path,
    expected_sections: int = 10,
    min_section_chars_no_spaces: int = 700,
) -> Metrics:
    text = read_docx_text(contract_docx)
    form = load_json(form_json)

    sections = split_into_top_sections(text)

    cov = metric_coverage(sections, expected_sections)
    num_ok, num_detail = metric_numbering_valid(sections)
    size_ok, size_detail = metric_section_size_ok(sections, min_section_chars_no_spaces)
    rep = metric_repetition_ratio(text)
    dup_count, dup_examples = metric_duplicate_sentences(text)

    pres = metric_parameter_presence(text, form)
    hall_count, hall_issues = metric_hallucination_count(text, form)

    details = {
        "numbering": num_detail,
        "section_sizes_no_spaces": size_detail,
        "duplicate_sentence_examples": dict(list(dup_examples.items())[:10]),
        "parameter_presence": {"matched": pres.matched, "missing": pres.missing},
        "hallucination_issues": hall_issues,
    }

    return Metrics(
        coverage=round(cov, 3),
        numbering_valid=num_ok,
        section_size_ok=size_ok,
        repetition_ratio=round(rep, 3),
        duplicate_sentences=dup_count,
        parameter_presence=round(pres.score, 3),
        hallucination_count=hall_count,
        details=details,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--contract", type=Path, required=True, help="Path to RU contract .docx")
    ap.add_argument("--form", type=Path, required=True, help="Path to form_input.json")
    ap.add_argument("--expected-sections", type=int, default=10)
    ap.add_argument("--min-section-chars", type=int, default=700, help="Min chars w/o spaces per top section")
    ap.add_argument("--out", type=Path, default=None, help="Optional output JSON file")
    args = ap.parse_args()

    m = evaluate(
        args.contract,
        args.form,
        expected_sections=args.expected_sections,
        min_section_chars_no_spaces=args.min_section_chars,
    )

    payload = {
        "Полнота_структуры": m.coverage,
        "Корректность_нумерации": m.numbering_valid,
        "Достаточный_объем_разделов": m.section_size_ok,
        "Коэффициент_лексического_разнообразия": m.repetition_ratio,
        "Количество_дословных_повторов": m.duplicate_sentences,
        "Соответствие_параметрам_формы": m.parameter_presence,
        "Количество_галлюцинаций": m.hallucination_count,
        "Детализация": m.details,
    }

    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
