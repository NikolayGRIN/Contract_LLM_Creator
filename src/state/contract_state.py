# src/state/contract_state.py
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict


@dataclass
class ContractState:
    data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def empty(cls, *, contract_type: str = "supply", language_mode: str = "en") -> "ContractState":
        return cls(
            data={
                "meta": {
                    "contract_type": contract_type,
                    "language_mode": language_mode,
                    "version": "v2"
                },

                # v2 commercial
                "commercial_terms": {
                    "currency": None,
                    "contract_price": None,
                    "vat_mode": None,
                    "price_basis": None,
                    "price_includes_packaging": None
                },

                # v2 goods / subject
                "goods": {
                    "goods_description": None,
                    "quantity": None,
                    "specification_ref": None,
                    "country_of_origin_required": None
                },

                # payment
                "payment_terms": {
                    "payment_due_days": None,
                    "payment_trigger": None,
                    "prepayment_required": None,
                    "prepayment_amount": None,
                    "prepayment_currency": None,
                    "bank_details_included": None,
                    "withholding_allowed": None,
                    "suspension_right": None,
                    "bank_charges": None,
                    "late_payment_penalty_enabled": None,
                    "late_payment_penalty_rate": None,

                    # new: details block (adds content density)
                    "details": {
                        "invoice_format": None,
                        "supporting_documents": [],
                        "partial_payments_allowed": None,
                        "overpayment_rule": None,
                        "disputed_amounts_rule": None
                    }
                },

                # delivery
                "delivery_terms": {
                    "delivery_date_type": None,
                    "delivery_days": None,
                    "delivery_place": None,
                    "partial_shipments_allowed": None,
                    "incoterms": None,
                    "incoterms_version": None,

                    "details": {
                        "packaging_standard": None,
                        "marking_standard": None,
                        "carrier_selection": None,
                        "loading_party": None,
                        "unloading_party": None,
                        "delivery_documents": [],
                        "delivery_schedule_rule": None
                    }
                },

                # acceptance
                "acceptance": {
                    "acceptance_required": None,
                    "acceptance_period_days": None,
                    "acceptance_document": None,
                    "acceptance_rules": None,
                    "documents_required": [],

                    "details": {
                        "inspection_scope": None,
                        "defect_notice_method": None,
                        "silent_acceptance_rule": None,
                        "remedy_options": [],
                        "remedy_time_days": None
                    }
                },

                # warranties
                "warranties": {
                    "warranty_period_months": None,
                    "warranty_start": None,
                    "remedy": None,
                    "response_time_days": None,

                    "details": {
                        "covered_defects": None,
                        "excluded_cases": [],
                        "service_location": None,
                        "spare_parts_rule": None
                    }
                },

                # liability
                "liability_terms": {
                    "liability_cap_enabled": None,
                    "liability_cap_type": None,
                    "cap_scope": None,
                    "indirect_damages_excluded": None,
                    "exceptions_to_cap": [],
                    "delay_in_delivery_penalty_enabled": None,
                    "claim_notice_days": None,

                    "details": {
                        "general_rule": None,
                        "delay_penalty": {
                            "enabled": None,
                            "rate": None,
                            "one_time_fine_rate": None,
                            "max_percent": None
                        },
                        "defective_goods_penalty": {
                            "enabled": None,
                            "fine_percent": None
                        },
                        "documents_delay_penalty": {
                            "enabled": None,
                            "fine_amount_per_day": None
                        },
                        "penalty_payment_procedure": None,
                        "penalty_no_release_clause": None,
                        "claim_procedure_notes": None
                    }
                },

                # legal
                "legal_terms": {
                    "governing_law": None,
                    "dispute_resolution": None,
                    "court_place": None,
                    "arbitration_seat": None,
                    "force_majeure_notice_days": None,

                    "details": {
                        "pretrial_negotiation": None,
                        "pretrial_term_days": None
                    }
                },

                "consistency": {
                    "conflicts": [],
                    "warnings": []
                },

                "parties": {
                    "seller": {"name": None, "role_label_en": "Seller", "role_label_ru": "Продавец"},
                    "buyer": {"name": None, "role_label_en": "Buyer", "role_label_ru": "Покупатель"}
                }
            }
        )

    @classmethod
    def load(cls, path: Path) -> "ContractState":
        return cls(data=json.loads(path.read_text(encoding="utf-8")))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

    def get(self, dotted_path: str, default: Any = None) -> Any:
        cur: Any = self.data
        for part in dotted_path.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur

    def set(self, dotted_path: str, value: Any) -> None:
        cur = self.data
        parts = dotted_path.split(".")
        for p in parts[:-1]:
            cur = cur.setdefault(p, {})
        cur[parts[-1]] = value


def bootstrap_state_from_form(form: Dict[str, Any], *, state: ContractState) -> ContractState:
    """
    Backward-compatible bootstrap.

    Priority:
      1) v2 blocks (commercial/goods/acceptance/warranties/legal + *_details)
      2) legacy v1 fields (currency top-level, payment.vat_mode, delivery.acceptance_*)
    """

    def pick(*paths, default=None):
        for path in paths:
            cur: Any = form
            ok = True
            for part in path.split("."):
                if isinstance(cur, dict) and part in cur:
                    cur = cur[part]
                else:
                    ok = False
                    break
            if ok and cur is not None:
                return cur
        return default

    # -----------------
    # meta
    # -----------------
    state.set("meta.contract_type", form.get("contract_type", "supply"))
    state.set("meta.language_mode", str(form.get("language_mode", "ru")).lower())

    # -----------------
    # commercial
    # -----------------
    state.set("commercial_terms.currency", pick("commercial.currency", "currency"))
    state.set("commercial_terms.contract_price", pick("commercial.contract_price"))
    state.set("commercial_terms.vat_mode", pick("commercial.vat_mode", "payment.vat_mode"))
    state.set("commercial_terms.price_basis", pick("commercial.price_basis"))
    state.set("commercial_terms.price_includes_packaging", pick("commercial.price_includes_packaging"))

    # -----------------
    # goods
    # -----------------
    state.set("goods.goods_description", pick("goods.goods_description"))
    state.set("goods.quantity", pick("goods.quantity"))
    state.set("goods.specification_ref", pick("goods.specification_ref"))
    state.set("goods.country_of_origin_required", pick("goods.country_of_origin_required"))

    # -----------------
    # payment (core)
    # -----------------
    state.set("payment_terms.payment_due_days", pick("payment.payment_term_days", "payment.payment_due_days"))
    state.set("payment_terms.payment_trigger", pick("payment.payment_trigger"))
    state.set("payment_terms.prepayment_required", pick("payment.prepayment_required"))
    state.set("payment_terms.prepayment_amount", pick("payment.prepayment_amount"))
    state.set("payment_terms.prepayment_currency", pick("payment.prepayment_currency", "commercial.currency", "currency"))
    state.set("payment_terms.bank_details_included", pick("payment.bank_details_included"))
    state.set("payment_terms.withholding_allowed", pick("payment.withholding_allowed"))
    state.set("payment_terms.suspension_right", pick("payment.suspension_right"))
    state.set("payment_terms.bank_charges", pick("payment.bank_charges"))
    state.set("payment_terms.late_payment_penalty_enabled", pick("payment.late_payment_penalty_enabled"))
    state.set("payment_terms.late_payment_penalty_rate", pick("payment.late_payment_penalty_rate"))

    # payment details
    state.set("payment_terms.details.invoice_format", pick("payment.payment_details.invoice_format"))
    state.set("payment_terms.details.supporting_documents", pick("payment.payment_details.supporting_documents", default=[]))
    state.set("payment_terms.details.partial_payments_allowed", pick("payment.payment_details.partial_payments_allowed"))
    state.set("payment_terms.details.overpayment_rule", pick("payment.payment_details.overpayment_rule"))
    state.set("payment_terms.details.disputed_amounts_rule", pick("payment.payment_details.disputed_amounts_rule"))

    if state.get("payment_terms.details.supporting_documents") is None:
        state.set("payment_terms.details.supporting_documents", [])

    # -----------------
    # delivery (core)
    # -----------------
    state.set("delivery_terms.delivery_date_type", pick("delivery.delivery_date_type"))
    state.set("delivery_terms.delivery_days", pick("delivery.delivery_within_days", "delivery.delivery_days"))
    state.set("delivery_terms.delivery_place", pick("delivery.delivery_place"))
    state.set("delivery_terms.partial_shipments_allowed", pick("delivery.partial_shipments_allowed"))
    state.set("delivery_terms.incoterms", pick("delivery.incoterms"))
    state.set("delivery_terms.incoterms_version", pick("delivery.incoterms_version"))

    # delivery details
    state.set("delivery_terms.details.packaging_standard", pick("delivery.delivery_details.packaging_standard"))
    state.set("delivery_terms.details.marking_standard", pick("delivery.delivery_details.marking_standard"))
    state.set("delivery_terms.details.carrier_selection", pick("delivery.delivery_details.carrier_selection"))
    state.set("delivery_terms.details.loading_party", pick("delivery.delivery_details.loading_party"))
    state.set("delivery_terms.details.unloading_party", pick("delivery.delivery_details.unloading_party"))
    state.set("delivery_terms.details.delivery_documents", pick("delivery.delivery_details.delivery_documents", default=[]))
    state.set("delivery_terms.details.delivery_schedule_rule", pick("delivery.delivery_details.delivery_schedule_rule"))

    if state.get("delivery_terms.details.delivery_documents") is None:
        state.set("delivery_terms.details.delivery_documents", [])

    # -----------------
    # acceptance (v2 or legacy delivery.*)
    # -----------------
    state.set("acceptance.acceptance_required", pick("acceptance.acceptance_required", "delivery.acceptance_required"))
    state.set("acceptance.acceptance_period_days", pick("acceptance.acceptance_period_days", "delivery.acceptance_period_days"))
    state.set("acceptance.acceptance_document", pick("acceptance.acceptance_document", "delivery.acceptance_document"))
    state.set("acceptance.acceptance_rules", pick("acceptance.acceptance_rules", "delivery.acceptance_rules"))
    state.set("acceptance.documents_required", pick("acceptance.documents_required", default=[]))

    # acceptance details
    state.set("acceptance.details.inspection_scope", pick("acceptance.acceptance_details.inspection_scope"))
    state.set("acceptance.details.defect_notice_method", pick("acceptance.acceptance_details.defect_notice_method"))
    state.set("acceptance.details.silent_acceptance_rule", pick("acceptance.acceptance_details.silent_acceptance_rule"))
    state.set("acceptance.details.remedy_options", pick("acceptance.acceptance_details.remedy_options", default=[]))
    state.set("acceptance.details.remedy_time_days", pick("acceptance.acceptance_details.remedy_time_days"))

    if state.get("acceptance.documents_required") is None:
        state.set("acceptance.documents_required", [])
    if state.get("acceptance.details.remedy_options") is None:
        state.set("acceptance.details.remedy_options", [])

    # -----------------
    # warranties
    # -----------------
    state.set("warranties.warranty_period_months", pick("warranties.warranty_period_months"))
    state.set("warranties.warranty_start", pick("warranties.warranty_start"))
    state.set("warranties.remedy", pick("warranties.remedy"))
    state.set("warranties.response_time_days", pick("warranties.response_time_days"))

    # warranty details
    state.set("warranties.details.covered_defects", pick("warranties.warranty_details.covered_defects"))
    state.set("warranties.details.excluded_cases", pick("warranties.warranty_details.excluded_cases", default=[]))
    state.set("warranties.details.service_location", pick("warranties.warranty_details.service_location"))
    state.set("warranties.details.spare_parts_rule", pick("warranties.warranty_details.spare_parts_rule"))

    if state.get("warranties.details.excluded_cases") is None:
        state.set("warranties.details.excluded_cases", [])

    # -----------------
    # liability (core)
    # -----------------
    state.set("liability_terms.liability_cap_enabled", pick("liability.liability_cap_enabled"))
    state.set("liability_terms.liability_cap_type", pick("liability.liability_cap_type"))
    state.set("liability_terms.cap_scope", pick("liability.cap_scope"))
    state.set("liability_terms.indirect_damages_excluded", pick("liability.indirect_damages_excluded"))
    state.set("liability_terms.exceptions_to_cap", pick("liability.exceptions_to_cap", default=[]))
    state.set("liability_terms.delay_in_delivery_penalty_enabled", pick("liability.delay_in_delivery_penalty_enabled"))
    state.set("liability_terms.claim_notice_days", pick("liability.claim_notice_days"))

    if state.get("liability_terms.exceptions_to_cap") is None:
        state.set("liability_terms.exceptions_to_cap", [])

    # liability details
    state.set("liability_terms.details.general_rule", pick("liability.liability_details.general_rule"))
    state.set("liability_terms.details.penalty_payment_procedure", pick("liability.liability_details.penalty_payment_procedure"))
    state.set("liability_terms.details.penalty_no_release_clause", pick("liability.liability_details.penalty_no_release_clause"))
    state.set("liability_terms.details.claim_procedure_notes", pick("liability.liability_details.claim_procedure_notes"))

    # nested penalties
    state.set("liability_terms.details.delay_penalty.enabled", pick("liability.liability_details.delay_penalty.enabled"))
    state.set("liability_terms.details.delay_penalty.rate", pick("liability.liability_details.delay_penalty.rate"))
    state.set("liability_terms.details.delay_penalty.one_time_fine_rate", pick("liability.liability_details.delay_penalty.one_time_fine_rate"))
    state.set("liability_terms.details.delay_penalty.max_percent", pick("liability.liability_details.delay_penalty.max_percent"))

    state.set("liability_terms.details.defective_goods_penalty.enabled", pick("liability.liability_details.defective_goods_penalty.enabled"))
    state.set("liability_terms.details.defective_goods_penalty.fine_percent", pick("liability.liability_details.defective_goods_penalty.fine_percent"))

    state.set("liability_terms.details.documents_delay_penalty.enabled", pick("liability.liability_details.documents_delay_penalty.enabled"))
    state.set("liability_terms.details.documents_delay_penalty.fine_amount_per_day", pick("liability.liability_details.documents_delay_penalty.fine_amount_per_day"))

    # -----------------
    # legal
    # -----------------
    state.set("legal_terms.governing_law", pick("legal.governing_law"))
    state.set("legal_terms.dispute_resolution", pick("legal.dispute_resolution"))
    state.set("legal_terms.court_place", pick("legal.court_place"))
    state.set("legal_terms.arbitration_seat", pick("legal.arbitration_seat"))
    state.set("legal_terms.force_majeure_notice_days", pick("legal.force_majeure_notice_days"))

    # legal details
    state.set("legal_terms.details.pretrial_negotiation", pick("legal.legal_details.pretrial_negotiation"))
    state.set("legal_terms.details.pretrial_term_days", pick("legal.legal_details.pretrial_term_days"))

    return state
