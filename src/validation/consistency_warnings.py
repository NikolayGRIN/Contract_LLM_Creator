# src/validation/consistency_warnings.py
from __future__ import annotations
from typing import Dict, Any, List

def warn_payment_terms(text: str, form: Dict[str, Any]) -> List[str]:
    warnings: List[str] = []
    # примеры мягких проверок (НЕ стопим генерацию)
    if form.get("commercial", {}).get("currency") == "RUB":
        t = text.lower()
        if ("rub" not in t) and ("руб" not in t):
            warnings.append("PaymentTerms: currency=RUB but RUB/руб not mentioned.")
    if form.get("payment", {}).get("withholding_allowed") is False:
        if "удержан" in text.lower() and ("допуска" in text.lower() or "разреш" in text.lower()):
            warnings.append("PaymentTerms: withholding_allowed=false but text may allow withholding.")
    return warnings

def warn_delivery_terms(text: str, form: Dict[str, Any]) -> List[str]:
    warnings: List[str] = []
    delivery = (form.get("delivery") or {})
    days = delivery.get("delivery_within_days")
    if isinstance(days, int) and str(days) not in text:
        warnings.append(f"DeliveryTerms: delivery_within_days={days} not found in text.")
    return warnings
