from __future__ import annotations

import re
from typing import Callable, Optional


def _strip_spaces(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def delivery_terms_validator(
    *,
    min_chars_no_spaces: int = 900,
    min_subclauses: int = 20,
) -> Callable[[str], Optional[str]]:
    """
    Delivery Terms validator (Variant A):
    - WITHOUT numbering enforcement (numbering is added later by ensure_numbered_lines)
    - WITH min_chars_no_spaces
    - WITH minimum subclauses count (by lines)
    - WITH anti-duplication
    - WITH leakage protection (payment / disputes)
    """

    # ----------------------------
    # Forbidden topic leakage
    # ----------------------------
    forbidden_patterns = [
        # payment leakage (RU)
        r"\bоплат", r"\bплатеж", r"\bплатёж",
        r"\bпредоплат", r"\bаванс",
        r"\bпен(я|и)\b", r"\bнеусто(йка|ек)\b", r"\bштраф\b",
        r"\bпроцен(т|ты)\s+за\s+просроч",

        # payment leakage (EN)
        r"\bpayment\b", r"\bpayable\b", r"\bdue\s+date\b",
        r"\bwithholding\b", r"\bset[-\s]?off\b",
        r"\blate\s+payment\b", r"\bdefault\s+interest\b",

        # disputes leakage (RU/EN)
        r"\bсуд\b", r"\bарбитраж\b", r"\bпретензи", r"\bисков", r"\bюрисдикц",
        r"\bcourt\b", r"\barbitration\b", r"\bclaim\b", r"\bdispute\b",
    ]
    forbidden_re = re.compile("|".join(forbidden_patterns), flags=re.IGNORECASE)

    # ----------------------------
    # Anti-duplication helpers
    # ----------------------------
    def _fingerprint(line: str) -> str:
        low = re.sub(r"[^a-zа-я0-9\s]", " ", (line or "").lower())
        words = [w for w in low.split() if w]
        return " ".join(words[:8])

    # внутренняя мусорная нумерация типа "1. The goods..."
    inner_simple_number_re = re.compile(r"\b\d+\.\s+[A-Za-zА-Яа-я]")

    def _validate(text: str) -> Optional[str]:
        t = (text or "").strip()
        if not t:
            return "empty_output"

        # 1) минимальная длина (БЕЗ пробелов)
        if len(_strip_spaces(t)) < int(min_chars_no_spaces):
            return "too_short"

        # 2) строки = будущие подпункты
        lines = [ln.strip() for ln in t.splitlines() if ln.strip()]

        if len(lines) < int(min_subclauses):
            return "too_few_list_items"

        # 3) leakage других секций
        if len(forbidden_re.findall(t)) >= 3:
            return "forbidden_topic_detected"

        # 4) повторы
        fp_counts = {}
        for ln in lines:
            fp = _fingerprint(ln)
            if not fp:
                continue
            fp_counts[fp] = fp_counts.get(fp, 0) + 1

        if any(c >= 4 for c in fp_counts.values()):
            return "repetition_detected"

        
        return None

    return _validate
