from __future__ import annotations

import re
from typing import Callable, Optional


def _strip_spaces(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def _fingerprint(line: str) -> str:
    """
    Нормализованный префикс строки (для ловли повторов шаблонов).
    Берём первые ~8 слов → устойчиво ловит loop-генерацию.
    """
    low = re.sub(r"[^a-zа-я0-9\s]", " ", (line or "").lower())
    words = [w for w in low.split() if w]
    return " ".join(words[:8])


# -----------------------------------------------------------
# main validator
# -----------------------------------------------------------

def payment_terms_validator(
    *,
    bank_details_included: bool,
    late_payment_penalty_enabled: bool,
    min_chars_no_spaces: int = 850,
    min_subclauses: int = 20,
) -> Callable[[str], Optional[str]]:
    
    # ---- strict bank details ----
    bank_re = re.compile(
        r"\b(р/с|к/с|бик|инн|кпп|огрн|swift|iban|account\s+no|beneficiary)\b",
        flags=re.IGNORECASE,
    )

    # ---- penalty words ----
    penalty_re = re.compile(
        r"\b(пеня|пени|неустойк|штраф|процент(ы)?\s+за\s+просроч|penalt|fine|default\s+interest|late\s+payment\s+interest|interest\s+for\s+late\s+payment|interest\s+on\s+late\s+payments)\b",
        flags=re.IGNORECASE,
    )

    # ---- detects "two sentences in one line" ----
    multi_sentence_re = re.compile(r"[.!?]\s+[A-ZА-ЯЁ]")

    # ---- numbering like "4.1. 1. Text" (inner explosion) ----
    inner_numbering_re = re.compile(r"\b\d+\.\s+[A-Za-zА-Яа-я]")

    def _validate(text: str) -> Optional[str]:
        t = (text or "").strip()
        if not t:
            return "empty_output"

        # -------------------------------------------------------
        # length
        # -------------------------------------------------------
        if len(_strip_spaces(t)) < int(min_chars_no_spaces):
            return "too_short"

        # -------------------------------------------------------
        # split lines (1 line = 1 clause)
        # -------------------------------------------------------
        lines = [ln.strip() for ln in t.splitlines() if ln.strip()]

        # remove accidental headers
        lines = [
            ln for ln in lines
            if not re.match(r"^(payment terms|условия оплаты)\b", ln, flags=re.I)
        ]

        if len(lines) < int(min_subclauses):
            return "too_few_list_items"

        
        fp_counts = {}
        for ln in lines:
            fp = _fingerprint(ln)
            if fp:
                fp_counts[fp] = fp_counts.get(fp, 0) + 1

        # если 5+ строк начинаются одинаково → LLM loop
        if any(c >= 3 for c in fp_counts.values()):
            return "repetition_detected"

        # -------------------------------------------------------
        # business rules
        # -------------------------------------------------------
        if (not bank_details_included) and bank_re.search(t):
            return "bank_details_detected"

        if (not late_payment_penalty_enabled) and penalty_re.search(t):
            return "late_payment_penalty_detected"

        return None

    return _validate
