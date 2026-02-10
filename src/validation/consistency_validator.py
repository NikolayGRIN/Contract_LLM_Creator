from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Callable, Dict, Any, List, Tuple, Optional


ValidatorFn = Callable[[str], Optional[str]]  # return None if OK else error string
WarningSink = Optional[Callable[[str], None]]


# ----------------------------
# Utilities
# ----------------------------
_re_num = re.compile(r"^\s*(\d+)\.(\d+)\.\s+")
_re_space = re.compile(r"\s+")
_re_punct = re.compile(r"[^\w\s]+", re.UNICODE)


def _norm_line(s: str) -> str:
    s = (s or "").strip().lower()
    s = _re_punct.sub(" ", s)
    s = _re_space.sub(" ", s).strip()
    return s


def _extract_numbered_lines(text: str, prefix: str) -> List[str]:
    """
    Extract lines starting with "<prefix>.<n>." e.g. "1.1." or "2.14."
    """
    out: List[str] = []
    for line in (text or "").splitlines():
        line = line.rstrip()
        if re.match(rf"^\s*{re.escape(prefix)}\.\d+\.\s+", line):
            out.append(line.strip())
    return out


def _find_near_duplicates(lines: List[str], *, ratio: float = 0.92) -> List[Tuple[int, int, float]]:
    """
    Return list of (i, j, sim) for near-duplicate normalized lines.
    """
    normed = [_norm_line(x) for x in lines]
    pairs: List[Tuple[int, int, float]] = []
    for i in range(len(normed)):
        for j in range(i + 1, len(normed)):
            if not normed[i] or not normed[j]:
                continue
            sim = SequenceMatcher(None, normed[i], normed[j]).ratio()
            if sim >= ratio:
                pairs.append((i, j, sim))
    return pairs


def _has_any(text: str, patterns: List[str]) -> bool:
    t = (text or "").lower()
    return any((p or "").lower() in t for p in patterns)


def _get(form: Dict[str, Any], path: str, default=None):
    cur: Any = form
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


# ----------------------------
# Composition
# ----------------------------
def compose_validators(*validators: ValidatorFn) -> ValidatorFn:
    def _v(text: str) -> Optional[str]:
        for fn in validators:
            err = fn(text)
            if err:
                return err
        return None
    return _v


# ----------------------------
# Internal helper: soft/hard emit
# ----------------------------
def _emit(
    msg: str,
    *,
    mode: str,
    on_warning: WarningSink,
) -> Optional[str]:
    """
    mode:
      - "warn": log to sink and return None
      - "hard": return msg (blocking)
    """
    m = (mode or "warn").strip().lower()
    if m == "warn":
        if on_warning is not None:
            try:
                on_warning(msg)
            except Exception:
                pass
        return None
    return msg


# ----------------------------
# Payment consistency
# ----------------------------
@dataclass(frozen=True)
class PaymentConsistencyConfig:
    currency: Optional[str]
    payment_term_days: Optional[int]
    withholding_allowed: Optional[bool]
    suspension_right: Optional[bool]
    bank_details_included: Optional[bool]
    late_payment_penalty_enabled: Optional[bool]


def make_payment_consistency_validator(
    form: Dict[str, Any],
    *,
    min_unique_lines: int = 18,
    mode: str = "warn",
    on_warning: WarningSink = None,
) -> ValidatorFn:
    cfg = PaymentConsistencyConfig(
        currency=_get(form, "commercial.currency", _get(form, "currency")),
        payment_term_days=_get(form, "payment.payment_term_days"),
        withholding_allowed=_get(form, "payment.withholding_allowed"),
        suspension_right=_get(form, "payment.suspension_right"),
        bank_details_included=_get(form, "payment.bank_details_included"),
        late_payment_penalty_enabled=_get(form, "payment.late_payment_penalty_enabled"),
    )

    def _v(text: str) -> Optional[str]:
        # 1) duplicates control (for 1.x)
        lines = _extract_numbered_lines(text, prefix="1")
        if lines:
            near_dups = _find_near_duplicates(lines, ratio=0.92)
            if near_dups:
                sample = near_dups[:3]
                out = _emit(
                    f"Consistency: near-duplicate subclauses detected in Payment Terms: {sample}",
                    mode=mode,
                    on_warning=on_warning,
                )
                if out:
                    return out

            uniq = len({_norm_line(x) for x in lines})
            if uniq < min_unique_lines:
                out = _emit(
                    f"Consistency: too few unique Payment subclauses (unique={uniq}, expected>={min_unique_lines}).",
                    mode=mode,
                    on_warning=on_warning,
                )
                if out:
                    return out

        # 2) currency must be fixed if provided
        if cfg.currency:
            cur = str(cfg.currency).upper()
            t = (text or "").lower()
            if cur == "RUB":
                if not _has_any(text, ["руб", "rur", "rub", "российск"]):
                    out = _emit(
                        "Consistency: currency=RUB but Payment Terms do not mention RUB/руб.",
                        mode=mode,
                        on_warning=on_warning,
                    )
                    if out:
                        return out
                if _has_any(text, ["валюта платежа определяется договором", "валюта платежа определяется сторонами"]):
                    out = _emit(
                        "Consistency: currency is fixed in the form, but text says it is 'determined by the contract/parties'.",
                        mode=mode,
                        on_warning=on_warning,
                    )
                    if out:
                        return out
            else:
                if cur.lower() not in t and cur not in (text or ""):
                    out = _emit(
                        f"Consistency: currency={cur} but Payment Terms do not mention it.",
                        mode=mode,
                        on_warning=on_warning,
                    )
                    if out:
                        return out
                if _has_any(text, ["валюта платежа определяется договором", "валюта платежа определяется сторонами"]):
                    out = _emit(
                        "Consistency: currency is fixed in the form, but text says it is 'determined by the contract/parties'.",
                        mode=mode,
                        on_warning=on_warning,
                    )
                    if out:
                        return out

        # 3) payment term days must match
        if cfg.payment_term_days is not None:
            days = int(cfg.payment_term_days)
            if not re.search(rf"\b{days}\b", text or ""):
                out = _emit(
                    f"Consistency: payment_term_days={days} but Payment Terms do not contain '{days}'.",
                    mode=mode,
                    on_warning=on_warning,
                )
                if out:
                    return out

        # 4) withholding allowed
        if cfg.withholding_allowed is False:
            if re.search(r"удержан(ия|ий).*(допускают|разреш|возмож)", text or "", re.IGNORECASE):
                out = _emit(
                    "Consistency: withholding_allowed=false but Payment Terms allow withholding/set-off.",
                    mode=mode,
                    on_warning=on_warning,
                )
                if out:
                    return out
        if cfg.withholding_allowed is True:
            if re.search(r"удержан(ия|ий).*(не\s+допуска|запрещ)", text or "", re.IGNORECASE):
                out = _emit(
                    "Consistency: withholding_allowed=true but Payment Terms forbid withholding/set-off.",
                    mode=mode,
                    on_warning=on_warning,
                )
                if out:
                    return out

        # 5) suspension_right
        if cfg.suspension_right is True:
            if re.search(r"просрочк.*не\s+влечет.*приостан", text or "", re.IGNORECASE):
                out = _emit(
                    "Consistency: suspension_right=true but text says late payment does NOT entail suspension.",
                    mode=mode,
                    on_warning=on_warning,
                )
                if out:
                    return out
        if cfg.suspension_right is False:
            if re.search(r"(приостан(ов|авли)|suspend).*(поставк|исполнен)", text or "", re.IGNORECASE):
                out = _emit(
                    "Consistency: suspension_right=false but Payment Terms grant suspension right.",
                    mode=mode,
                    on_warning=on_warning,
                )
                if out:
                    return out

        # 6) bank_details_included (в учебном режиме лучше только warn)
        if cfg.bank_details_included is False:
            if re.search(r"\b(iban|swift|bic)\b", text or "", re.IGNORECASE) or re.search(
                r"(р/с|к/с|бик|расчетн(ый|ого)\s+счет)", text or "", re.IGNORECASE
            ):
                out = _emit(
                    "Consistency: bank_details_included=false but bank details appear in Payment Terms.",
                    mode=mode,
                    on_warning=on_warning,
                )
                if out:
                    return out

        # 7) late_payment_penalty_enabled
        if cfg.late_payment_penalty_enabled is False:
            if re.search(r"(пен(я|и)|неустойк|штраф).*(просрочк|задержк)", text or "", re.IGNORECASE):
                out = _emit(
                    "Consistency: late_payment_penalty_enabled=false but text mentions late payment penalties.",
                    mode=mode,
                    on_warning=on_warning,
                )
                if out:
                    return out

        return None

    return _v


# ----------------------------
# Delivery consistency
# ----------------------------
@dataclass(frozen=True)
class DeliveryConsistencyConfig:
    delivery_within_days: Optional[int]
    delivery_place: Optional[str]
    partial_shipments_allowed: Optional[bool]
    acceptance_required: Optional[bool]
    acceptance_period_days: Optional[int]


def make_delivery_consistency_validator(
    form: Dict[str, Any],
    *,
    min_unique_lines: int = 18,
    mode: str = "warn",
    on_warning: WarningSink = None,
) -> ValidatorFn:
    cfg = DeliveryConsistencyConfig(
        delivery_within_days=_get(form, "delivery.delivery_within_days"),
        delivery_place=_get(form, "delivery.delivery_place"),
        partial_shipments_allowed=_get(form, "delivery.partial_shipments_allowed"),
        acceptance_required=_get(form, "acceptance.acceptance_required", _get(form, "delivery.acceptance_required")),
        acceptance_period_days=_get(form, "acceptance.acceptance_period_days", _get(form, "delivery.acceptance_period_days")),
    )

    def _v(text: str) -> Optional[str]:
        # 1) duplicates control (for 2.x)
        lines = _extract_numbered_lines(text, prefix="2")
        if lines:
            near_dups = _find_near_duplicates(lines, ratio=0.92)
            if near_dups:
                sample = near_dups[:3]
                out = _emit(
                    f"Consistency: near-duplicate subclauses detected in Delivery Terms: {sample}",
                    mode=mode,
                    on_warning=on_warning,
                )
                if out:
                    return out

            uniq = len({_norm_line(x) for x in lines})
            if uniq < min_unique_lines:
                out = _emit(
                    f"Consistency: too few unique Delivery subclauses (unique={uniq}, expected>={min_unique_lines}).",
                    mode=mode,
                    on_warning=on_warning,
                )
                if out:
                    return out

        # 2) delivery days must match
        if cfg.delivery_within_days is not None:
            days = int(cfg.delivery_within_days)
            if not re.search(rf"\b{days}\b", text or ""):
                out = _emit(
                    f"Consistency: delivery_within_days={days} but Delivery Terms do not contain '{days}'.",
                    mode=mode,
                    on_warning=on_warning,
                )
                if out:
                    return out

        # 3) delivery place must appear (simple containment)
        if cfg.delivery_place:
            place = str(cfg.delivery_place).strip()
            if place and place.lower() not in (text or "").lower():
                if not (_has_any(text, ["склад"]) and _has_any(text, ["покупател"])):
                    out = _emit(
                        f"Consistency: delivery_place='{place}' but Delivery Terms do not mention it.",
                        mode=mode,
                        on_warning=on_warning,
                    )
                    if out:
                        return out

        # 4) partial shipments allowed/disallowed
        if cfg.partial_shipments_allowed is True:
            if re.search(r"(частичн(ая|ые)|по\s+частям).*(запрещ|не\s+допуска)", text or "", re.IGNORECASE):
                out = _emit(
                    "Consistency: partial_shipments_allowed=true but text forbids partial deliveries.",
                    mode=mode,
                    on_warning=on_warning,
                )
                if out:
                    return out
        if cfg.partial_shipments_allowed is False:
            if re.search(r"(частичн(ая|ые)|по\s+частям).*(разреш|допуска)", text or "", re.IGNORECASE):
                out = _emit(
                    "Consistency: partial_shipments_allowed=false but text allows partial deliveries.",
                    mode=mode,
                    on_warning=on_warning,
                )
                if out:
                    return out

        # 5) acceptance rules if required
        if cfg.acceptance_required is True:
            if not _has_any(text, ["приемк", "inspection", "acceptance", "акт"]):
                out = _emit(
                    "Consistency: acceptance_required=true but Delivery Terms do not mention acceptance/inspection.",
                    mode=mode,
                    on_warning=on_warning,
                )
                if out:
                    return out
            if cfg.acceptance_period_days is not None:
                days = int(cfg.acceptance_period_days)
                if not re.search(rf"\b{days}\b", text or ""):
                    out = _emit(
                        f"Consistency: acceptance_period_days={days} but Delivery Terms do not contain '{days}'.",
                        mode=mode,
                        on_warning=on_warning,
                    )
                    if out:
                        return out

        if cfg.acceptance_required is False:
            if re.search(r"(обязател).*акт|акт.*обязател", text or "", re.IGNORECASE):
                out = _emit(
                    "Consistency: acceptance_required=false but Delivery Terms make acceptance act mandatory.",
                    mode=mode,
                    on_warning=on_warning,
                )
                if out:
                    return out

        return None

    return _v
