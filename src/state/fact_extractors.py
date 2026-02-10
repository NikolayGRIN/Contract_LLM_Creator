# src/state/fact_extractors.py
from __future__ import annotations

import re
from typing import Any, Dict


def extract_payment_facts(text: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    m = re.search(r"(within|no later than)\s+(\d{1,3})\s+(calendar\s+)?days", text, re.IGNORECASE)
    if m:
        out["payment_due_days"] = int(m.group(2))

    m = re.search(r"(в\s+течение|не\s+позднее)\s+(\d{1,3})\s+(календарн(ых|ые)\s+)?дн", text, re.IGNORECASE)
    if m:
        out["payment_due_days"] = int(m.group(2))

    if re.search(r"\bUSD\b|\bUS\s*Dollars?\b|\bUnited\s+States\s+Dollars?\b", text, re.IGNORECASE):
        out["currency"] = "USD"
    elif re.search(r"\bEUR\b|\bEuro\b", text, re.IGNORECASE):
        out["currency"] = "EUR"
    elif re.search(r"\bRUB\b|\bRUR\b|\bруб", text, re.IGNORECASE):
        out["currency"] = "RUB"

    m = re.search(r"(\d+(\.\d+)?)\s*%.*(per\s+day|per\s+each\s+day|daily)", text, re.IGNORECASE)
    if m:
        out["late_payment_penalty_rate"] = f"{m.group(1)}% per day"

    m = re.search(r"(\d+(\.\d+)?)\s*%.*(за\s+каждый\s+день|в\s+день|ежедневно)", text, re.IGNORECASE)
    if m:
        out["late_payment_penalty_rate"] = f"{m.group(1)}% per day"

    return out


def extract_delivery_facts(text: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    m = re.search(r"\b(EXW|FCA|CPT|CIP|DAP|DPU|DDP|FAS|FOB|CFR|CIF)\b", text, re.IGNORECASE)
    if m:
        out["incoterms"] = m.group(1).upper()

    m = re.search(r"(within|no later than)\s+(\d{1,3})\s+(calendar\s+)?days", text, re.IGNORECASE)
    if m:
        out["delivery_days"] = int(m.group(2))

    m = re.search(r"(в\s+течение|не\s+позднее)\s+(\d{1,3})\s+(календарн(ых|ые)\s+)?дн", text, re.IGNORECASE)
    if m:
        out["delivery_days"] = int(m.group(2))

    m = re.search(r"\bto\s+([A-Z][^\n\.;]{3,80})", text)
    if m:
        out["delivery_place"] = m.group(1).strip()

    m = re.search(r"\bв\s+([А-ЯЁ][^\n\.;]{3,80})", text)
    if m:
        out["delivery_place"] = m.group(1).strip()

    return out
