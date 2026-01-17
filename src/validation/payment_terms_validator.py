from __future__ import annotations

import re
from typing import Callable, Optional, List


def _strip_spaces(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def _extract_numbered_subclauses(text: str) -> List[str]:
    
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    pat = re.compile(r"^\s*\d+\.\d+\.\s+")
    return [ln for ln in lines if pat.match(ln)]


def payment_terms_validator(
    *,
    bank_details_included: bool,
    late_payment_penalty_enabled: bool,
    min_chars_no_spaces: int = 850,
    min_subclauses: int = 20,
) -> Callable[[str], Optional[str]]:
    
    # строгие признаки реквизитов (конкретика)
    bank_patterns_strict = [
        r"\bр/с\b", r"\bк/с\b",
        r"\bбик\b", r"\bинн\b", r"\bкпп\b", r"\bогрн\b",
        r"\bswift\b", r"\biban\b",
        r"\baccount\s+no\b", r"\bbeneficiary\b",
        r"\bрасч[её]тн(ый|ого)\s+сч[её]т\b\s*[:№]?\s*\d{10,}",   
        r"\bкорр(еспондентский)?\s+сч[её]т\b\s*[:№]?\s*\d{10,}",
    ]

    penalty_patterns = [
        r"\bпен(я|и)\b", r"\bнеусто(йка|ек)\b", r"\bштраф\b",
        r"\bпроцен(т|ты)\s+за\s+просроч", r"\blate\s+payment\b", r"\bdefault\s+interest\b",
    ]

    bank_re = re.compile("|".join(bank_patterns_strict), flags=re.IGNORECASE)
    penalty_re = re.compile("|".join(penalty_patterns), flags=re.IGNORECASE)

    def _validate(text: str) -> Optional[str]:
        t = (text or "").strip()
        if not t:
            return "empty_output"

        if len(_strip_spaces(t)) < int(min_chars_no_spaces):
            return "too_short"

        subclauses = _extract_numbered_subclauses(t)
        if len(subclauses) < int(min_subclauses):
            return "too_few_list_items"

        # detect wrong numbering like "1. ..." instead of "1.1. ..."
        bad_simple = 0
        good = 0
        for ln in (ln.strip() for ln in t.splitlines() if ln.strip()):
            if re.match(r"^\d+\.\s+", ln):
                bad_simple += 1
            if re.match(r"^\d+\.\d+\.\s+", ln):
                good += 1
        if good > 0 and bad_simple >= max(2, good // 2):
            return "wrong_numbering_format"
        
        if (not bank_details_included) and bank_re.search(t):
            return "bank_details_detected"
        
        if (not late_payment_penalty_enabled) and penalty_re.search(t):
            return "late_payment_penalty_detected"

        return None

    return _validate
