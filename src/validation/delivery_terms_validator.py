from __future__ import annotations

import re
from typing import Callable, Optional, List


def _strip_spaces(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def _extract_numbered_subclauses(text: str, *, prefix: str) -> List[str]:
    
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    
    pat = re.compile(
        rf"^\s*{re.escape(prefix)}\.(\d{{1,3}})\s*(?:[.)\-–])?\s+"
    )

    return [ln for ln in lines if pat.match(ln)]


def delivery_terms_validator(
    *,
    min_chars_no_spaces: int = 900,
    min_subclauses: int = 20,
    prefix: str = "2",
) -> Callable[[str], Optional[str]]:
    
    # запрещаем появление других секций (только самое явное)
    forbidden = [
        # оплата 
        r"\bоплат", r"\bплатеж", r"\bплатёж", r"\bсчет\b", r"\bсч[её]т\b", r"\binvoice\b",
        r"\bпен(я|и)\b", r"\bнеусто(йка|ек)\b", r"\bштраф\b",
        # суды 
        r"\bсуд\b", r"\bарбитраж\b", r"\bпретензи",
    ]
    forbidden_re = re.compile("|".join(forbidden), flags=re.IGNORECASE)

    def _validate(text: str) -> Optional[str]:
        t = (text or "").strip()
        if not t:
            return "empty_output"

        if len(_strip_spaces(t)) < int(min_chars_no_spaces):
            return "too_short"

        subclauses = _extract_numbered_subclauses(t, prefix=prefix)
        if len(subclauses) < int(min_subclauses):
            return "too_few_list_items"

        forbidden_hits = len(forbidden_re.findall(t))

        if forbidden_hits >= 3:
            return "forbidden_topic_detected"

        return None

    return _validate


