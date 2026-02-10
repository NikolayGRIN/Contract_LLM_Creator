# src/evaluation/eval_generation.py
from __future__ import annotations

import argparse
import json
import re
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ----------------------------
# IO
# ----------------------------
def read_jsonl(path: Path) -> List[dict]:
    out = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out

def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


# ----------------------------
# Text utilities
# ----------------------------
def norm(s: str) -> str:
    s = (s or "").replace("\u00A0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def split_lines(section_text: str) -> List[str]:
    # keep only non-empty lines
    lines = [(l or "").strip() for l in (section_text or "").splitlines()]
    return [l for l in lines if l]

def strip_leading_numbering(line: str) -> str:
    # remove "4.1." / "4.1" / "4)" etc.
    return re.sub(r"^\s*\d+(\.\d+)*[.)]?\s*", "", line).strip()

def prefix_key(line: str, n_words: int = 3) -> str:
    t = strip_leading_numbering(line).lower()
    words = re.findall(r"[A-Za-zА-Яа-я0-9]+", t)
    return " ".join(words[:n_words])


# ----------------------------
# Similarity (Jaccard on 3-grams) for near-duplicates
# ----------------------------
def trigrams(s: str) -> set:
    s = re.sub(r"\s+", " ", (s or "").lower()).strip()
    if len(s) < 3:
        return {s} if s else set()
    return {s[i:i+3] for i in range(len(s) - 2)}

def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    uni = len(a | b)
    return inter / (uni or 1)


# ----------------------------
# Forbidden leakage dictionaries (minimal, tune later)
# ----------------------------
FORBIDDEN = {
    # payment_terms should not talk about warranty/acceptance/delivery
    "payment_terms": [
        r"\bгаранти", r"\bwarranty\b",
        r"\bприемк", r"\bacceptance\b", r"\binspection\b",
        r"\bпоставк", r"\bdelivery\b", r"\bshipment\b",
    ],
    # delivery_terms should not talk about payment/interest/penalties
    "delivery_terms": [
        r"\bоплат", r"\bpayment\b", r"\binvoice\b",
        r"\bпен", r"\binterest\b", r"\bpenalt",
    ],
}

def forbidden_leakage_count(section_id: str, text: str) -> int:
    pats = FORBIDDEN.get(section_id, [])
    if not pats:
        return 0
    low = (text or "").lower()
    c = 0
    for p in pats:
        if re.search(p, low, flags=re.IGNORECASE):
            c += 1
    return c


# ----------------------------
# Constraint accuracy (payment/delivery only)
# ----------------------------
@dataclass
class ConstraintsResult:
    total: int
    ok: int
    details: Dict[str, bool]

CURRENCY_RE = re.compile(r"\b(usd|eur|cny|rmb|gbp|rub|aed)\b", re.IGNORECASE)

def extract_form_constraints(form: dict, section_id: str) -> Dict[str, Optional[str]]:
    """
    Returns key->expected string (or None if not available)
    """
    form = form or {}
    commercial = form.get("commercial") or {}

    if section_id == "payment_terms":
        p = form.get("payment") or {}
        currency = p.get("payment_currency") or p.get("currency") or commercial.get("currency") or form.get("currency")
        term_days = p.get("payment_term_days")
        prepay = p.get("prepayment_percent")
        return {
            "currency": str(currency) if currency else None,
            "payment_term_days": str(term_days) if term_days is not None else None,
            "prepayment_percent": str(prepay) if prepay is not None else None,
        }

    if section_id == "delivery_terms":
        d = form.get("delivery") or {}
        days = d.get("delivery_within_days") or d.get("delivery_term_days") or d.get("delivery_days")
        place = d.get("delivery_place")
        return {
            "delivery_days": str(days) if days is not None else None,
            "delivery_place": str(place) if place else None,
        }

    return {}

def check_constraints(section_id: str, text: str, form: Optional[dict]) -> ConstraintsResult:
    if not form:
        return ConstraintsResult(total=0, ok=0, details={})

    expects = extract_form_constraints(form, section_id)
    details: Dict[str, bool] = {}

    for k, v in expects.items():
        if v is None or v == "":
            continue
        low = (text or "").lower()
        if k == "currency":
            # accept either exact currency token or any currency match if form currency is short
            vlow = str(v).lower()
            ok = (vlow in low) or bool(CURRENCY_RE.search(low))
            details[k] = ok
        elif k in ("payment_term_days", "prepayment_percent", "delivery_days"):
            # digits must appear
            digits = re.findall(r"\d+", str(v))
            ok = any(d in low for d in digits) if digits else False
            details[k] = ok
        elif k == "delivery_place":
            vlow = normalize_place(v)
            ok = vlow in normalize_place(text)
            details[k] = ok
        else:
            details[k] = str(v).lower() in low

    total = len(details)
    ok = sum(1 for x in details.values() if x)
    return ConstraintsResult(total=total, ok=ok, details=details)

def normalize_place(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-zа-я0-9 ]+", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# ----------------------------
# Main metrics per section text
# ----------------------------
@dataclass
class SectionMetrics:
    subclauses: int
    repetition_prefix_rate: float
    near_duplicate_rate: float
    forbidden_leakage: int
    constraints_total: int
    constraints_ok: int

def compute_metrics(section_id: str, text: str, form: Optional[dict]) -> SectionMetrics:
    lines = split_lines(text)
    n = len(lines)

    # repetition prefix rate: share of lines whose 3-word prefix repeats >=2
    pref = [prefix_key(l, 3) for l in lines]
    pref = [p for p in pref if p]  # drop empty
    cnt = Counter(pref)
    repeated = sum(1 for p in pref if cnt[p] >= 2)
    repetition_rate = (repeated / (len(pref) or 1))

    # near-duplicate rate via trigram Jaccard
    # count pairs with similarity >= 0.85
    dup_pairs = 0
    total_pairs = 0
    grams = [trigrams(strip_leading_numbering(l)) for l in lines]
    for i in range(n):
        for j in range(i + 1, n):
            total_pairs += 1
            if jaccard(grams[i], grams[j]) >= 0.85:
                dup_pairs += 1
    near_dup_rate = (dup_pairs / (total_pairs or 1))

    leakage = forbidden_leakage_count(section_id, text)

    c = check_constraints(section_id, text, form)
    return SectionMetrics(
        subclauses=n,
        repetition_prefix_rate=repetition_rate,
        near_duplicate_rate=near_dup_rate,
        forbidden_leakage=leakage,
        constraints_total=c.total,
        constraints_ok=c.ok,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--generated", type=str, default="data/generated_sections.jsonl",
                    help="JSONL with fields: doc_id, section_id, method, language, text")
    ap.add_argument("--form", type=str, default="",
                    help="Optional form_input.json to evaluate constraint accuracy for payment/delivery")
    ap.add_argument("--only_sections", type=str, default="",
                    help="comma-separated filter by section_id")
    args = ap.parse_args()

    generated_path = Path(args.generated)
    rows = read_jsonl(generated_path)

    form = read_json(Path(args.form)) if args.form else None

    only = set()
    if args.only_sections.strip():
        only = {s.strip() for s in args.only_sections.split(",") if s.strip()}

    # aggregate by method and section_id
    agg = defaultdict(list)

    for r in rows:
        sid = (r.get("section_id") or "").strip()
        if only and sid not in only:
            continue
        method = (r.get("method") or "").strip() or "unknown"
        text = r.get("text", "")
        m = compute_metrics(sid, text, form)
        agg[(method, sid)].append(m)

    if not agg:
        print("ERROR: no rows matched (check --generated path or filters)")
        return 2

    print(f"Loaded: {len(rows)} sections from {generated_path}")
    if form:
        print("Form constraints: ENABLED (payment/delivery)")
    else:
        print("Form constraints: OFF (pass --form data/form_input.json to enable)")

    print()
    for (method, sid), ms in sorted(agg.items(), key=lambda x: (x[0][0], x[0][1])):
        n = len(ms)
        avg_sub = sum(x.subclauses for x in ms) / n
        avg_rep = sum(x.repetition_prefix_rate for x in ms) / n
        avg_dup = sum(x.near_duplicate_rate for x in ms) / n
        avg_leak = sum(x.forbidden_leakage for x in ms) / n

        tot_c = sum(x.constraints_total for x in ms)
        ok_c = sum(x.constraints_ok for x in ms)
        acc = (ok_c / tot_c) if tot_c else float("nan")

        print(f"[{method:10s}] {sid:24s} | n={n:3d} | subclauses={avg_sub:5.1f} | "
              f"rep_prefix={avg_rep:5.2f} | near_dup={avg_dup:5.2f} | leak={avg_leak:4.1f} | "
              f"constraint_acc={acc if not math.isnan(acc) else 'n/a'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
