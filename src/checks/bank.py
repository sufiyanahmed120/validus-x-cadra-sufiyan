"""BANK_MANDATE check (SOP 6.2, 6.3, TMF A2): verify payment account is registered.

TMF A2 (moved from TMF_ADDENDUM): TMF folios must follow additional bank validation.
For TMF folios, check if the SOP version is correct - TMF-ADD-02 from 15 Sep 2026.
v4.0 and TMF-ADD-01 are missing = PEND for TMF folios.
"""

import re
from datetime import datetime, timezone


def get_account_last4(account_str: str) -> str:
    if not account_str:
        return ""
    digits = re.sub(r"\D", "", account_str)
    return digits[-4:] if len(digits) >= 4 else digits


def check_bank(request: dict, extracted: dict, data: dict, resolved: dict) -> dict:
    bank_mandates = data.get("bank_mandates", [])
    folio_master = data.get("folio_master", [])
    transactions = data.get("transactions", [])

    folio_no = resolved.get("folio_no", "")
    txn_id = resolved.get("txn_id", "")

    # TMF A2: SOP version check for TMF folios (moved from TMF_ADDENDUM)
    if folio_no:
        fm_row = None
        for f in folio_master:
            if f.get("folio_no", "").strip() == folio_no:
                fm_row = f
                break
        if fm_row and (fm_row.get("amc_code", "") or "").strip() == "TMF":
            received_at_str = request.get("received_at", "")
            try:
                received_dt = datetime.fromisoformat(received_at_str)
                if received_dt.tzinfo is not None:
                    received_dt = received_dt.replace(tzinfo=None)
            except (ValueError, TypeError):
                received_dt = None

            if received_dt:
                add02_effective = datetime(2026, 9, 15)
                v41_effective = datetime(2026, 1, 1)
                if received_dt >= add02_effective or received_dt >= v41_effective:
                    pass
                else:
                    return {
                        "check": "BANK_MANDATE",
                        "result": "FAIL",
                        "reason_codes": ["TMF_A2_SOP_VERSION_MISSING"],
                        "proposed_outcome": "PEND",
                        "evidence": [{"source": "policy", "ref": "", "value": "TMF folio: v4.0 and TMF-ADD-01 are not available - PEND required"}],
                        "sop_clause": "TMF-ADD-02 / TMF A2",
                        "human_approval_required": "OPS_MANAGER"
                    }

    if not folio_no:
        return {
            "check": "BANK_MANDATE",
            "result": "NOT_APPLICABLE",
            "reason_codes": ["NEW_FOLIO"],
            "proposed_outcome": "PROCEED",
            "evidence": [],
            "sop_clause": "6.2",
            "human_approval_required": None
        }

    txn = None
    for t in transactions:
        if t.get("txn_id", "").strip() == txn_id:
            txn = t
            break

    if not txn:
        return {
            "check": "BANK_MANDATE",
            "result": "UNABLE_TO_VERIFY",
            "reason_codes": ["TXN_NOT_FOUND"],
            "proposed_outcome": "PEND",
            "evidence": [],
            "sop_clause": "6.2",
            "human_approval_required": "OPS_MANAGER"
        }

    payment_mode = (txn.get("payment_mode", "") or "").strip()
    remitter_account = (txn.get("remitter_account_masked", "") or "").strip()

    # TMF-ADD-02: TMF change of bank needs old-account proof, else BANK_PROOF_REQUIRED
    if not remitter_account and txn.get("txn_type", "").strip() in ("RED",):
        for f in folio_master:
            if f.get("folio_no", "").strip() == folio_no and (f.get("amc_code", "") or "").strip() == "TMF":
                cob_accounts = [b for b in bank_mandates if b.get("folio_no", "").strip() == folio_no
                                and (b.get("cob_request_received_on", "") or "").strip()]
                if cob_accounts:
                    return {
                        "check": "BANK_MANDATE",
                        "result": "FAIL",
                        "reason_codes": ["BANK_PROOF_REQUIRED"],
                        "proposed_outcome": "HOLD_AND_REFER",
                        "evidence": [{"source": "bank_mandates", "ref": folio_no, "value": "TMF change of bank - old-account proof required"}],
                        "sop_clause": "TMF-ADD-02",
                        "human_approval_required": None
                    }
                break

    # NACH, cheque - already have mandate
    if payment_mode in ("NACH", "CHEQUE", "DD"):
        return {
            "check": "BANK_MANDATE",
            "result": "PASS",
            "reason_codes": [f"MANDATE_MODE_{payment_mode}"],
            "proposed_outcome": "PROCEED",
            "evidence": [{"source": "transactions", "ref": txn_id, "value": f"Mode: {payment_mode}"}],
            "sop_clause": "6.2",
            "human_approval_required": None
        }

    if not remitter_account:
        if txn.get("txn_type", "").strip() in ("RED", "SWO"):
            cob_pending = [b for b in bank_mandates
                           if b.get("folio_no", "").strip() == folio_no
                           and (b.get("cob_request_received_on", "") or "").strip()]
            if cob_pending:
                return {
                    "check": "BANK_MANDATE",
                    "result": "FAIL",
                    "reason_codes": ["BANK_PROOF_REQUIRED"],
                    "proposed_outcome": "PEND",
                    "evidence": [{"source": "bank_mandates", "ref": folio_no, "value": "Redemption during a change of bank - new account proof / validation required"}],
                    "sop_clause": "6.3, 6.4",
                    "human_approval_required": None
                }
            return {
                "check": "BANK_MANDATE",
                "result": "PASS",
                "reason_codes": ["REDEMPTION_DEFAULT_ACCOUNT"],
                "proposed_outcome": "PROCEED",
                "evidence": [{"source": "transactions", "ref": txn_id, "value": "Redemption - no remitter"}],
                "sop_clause": "6.2",
                "human_approval_required": None
            }
        return {
            "check": "BANK_MANDATE",
            "result": "UNABLE_TO_VERIFY",
            "reason_codes": ["NO_REMITTER_ACCOUNT"],
            "proposed_outcome": "PEND",
            "evidence": [],
            "sop_clause": "6.2",
            "human_approval_required": None
        }

    # Check if account is registered on the folio
    folio_banks = [b for b in bank_mandates if b.get("folio_no", "").strip() == folio_no]
    account_l4 = get_account_last4(remitter_account)

    matched_bank = None
    for b in folio_banks:
        ba = (b.get("account_no_masked", "") or "").strip()
        if get_account_last4(ba) == account_l4:
            matched_bank = b
            break

    if matched_bank:
        status = (matched_bank.get("status", "") or "").strip()
        if status == "VALIDATED":
            return {
                "check": "BANK_MANDATE",
                "result": "PASS",
                "reason_codes": ["ACCOUNT_VALIDATED"],
                "proposed_outcome": "PROCEED",
                "evidence": [{"source": "bank_mandates", "ref": folio_no, "value": f"Account {remitter_account} VALIDATED"}],
                "sop_clause": "6.2",
                "human_approval_required": None
            }
        elif status == "PENDING_VALIDATION":
            return {
                "check": "BANK_MANDATE",
                "result": "FAIL",
                "reason_codes": ["ACCOUNT_PENDING_VALIDATION"],
                "proposed_outcome": "PEND",
                "evidence": [{"source": "bank_mandates", "ref": folio_no, "value": f"Account {remitter_account} PENDING_VALIDATION"}],
                "sop_clause": "6.2",
                "human_approval_required": None
            }
        elif status == "REJECTED":
            return {
                "check": "BANK_MANDATE",
                "result": "FAIL",
                "reason_codes": ["ACCOUNT_REJECTED"],
                "proposed_outcome": "REJECT",
                "evidence": [{"source": "bank_mandates", "ref": folio_no, "value": f"Account {remitter_account} REJECTED"}],
                "sop_clause": "6.2",
                "human_approval_required": None
            }

    # Account not registered on this folio
    # Check if it's the first holder's own account on another folio
    folio_row = None
    for f in folio_master:
        if f.get("folio_no", "").strip() == folio_no:
            folio_row = f
            break

    if folio_row:
        pan = folio_row.get("first_holder_pan_masked", "")
        # Check all bank mandates for this PAN across folios
        for f2 in folio_master:
            if f2.get("first_holder_pan_masked", "").replace("*", "").upper() == pan.replace("*", "").upper():
                f2_banks = [b for b in bank_mandates if b.get("folio_no", "").strip() == f2.get("folio_no", "").strip()]
                for b in f2_banks:
                    ba = (b.get("account_no_masked", "") or "").strip()
                    if get_account_last4(ba) == account_l4 and b.get("status", "").strip() == "VALIDATED":
                        return {
                            "check": "BANK_MANDATE",
                            "result": "PASS",
                            "reason_codes": ["ACCOUNT_ON_OTHER_FOLIO"],
                            "proposed_outcome": "PROCEED",
                            "evidence": [{"source": "bank_mandates", "ref": folio_no, "value": f"Account {remitter_account} valid on other folio"}],
                            "sop_clause": "6.2",
                            "human_approval_required": None
                        }

    # Own unregistered account: remitter name matches first holder or second holder, bank statement provided
    if folio_row:
        remitter_name = (txn.get("remitter_name", "") or "").strip().upper()
        first_holder_name = (folio_row.get("first_holder_name", "") or "").strip().upper()
        second_holder_name = (folio_row.get("second_holder_name", "") or "").strip().upper()
        remit_parts = set(remitter_name.replace(".", "").split())
        holder_parts = set(first_holder_name.replace(".", "").split())
        name_match = len(remit_parts & holder_parts) > 0
        if not name_match and second_holder_name:
            second_parts = set(second_holder_name.replace(".", "").split())
            name_match = len(remit_parts & second_parts) >= min(len(second_parts), 2)
        if name_match:
            # Second holder paying on joint/AS folio - allowed without extra proof
            holding_mode = (folio_row.get("holding_mode", "") or "").strip()
            if second_holder_name and holding_mode in ("JO", "AS"):
                second_parts = set(second_holder_name.replace(".", "").split())
                is_second = len(remit_parts & second_parts) >= min(len(second_parts), 2)
                if is_second:
                    return {
                        "check": "BANK_MANDATE",
                        "result": "PASS",
                        "reason_codes": ["SECOND_HOLDER_PAYMENT"],
                        "proposed_outcome": "PROCEED",
                        "evidence": [{"source": "folio_master", "ref": folio_no, "value": f"Second holder {second_holder_name} paid on {holding_mode} folio"}],
                        "sop_clause": "6.2",
                        "human_approval_required": None
                    }
            attachments = request.get("attachments", [])
            has_statement = any("STATEMENT" in (a.get("file_name", "") or "").upper() or "EXTRACT" in (a.get("file_name", "") or "").upper() for a in attachments)
            if has_statement:
                return {
                    "check": "BANK_MANDATE",
                    "result": "PASS",
                    "reason_codes": ["OWN_ACCOUNT_WITH_STATEMENT"],
                    "proposed_outcome": "PROCEED",
                    "evidence": [{"source": "bank_mandates", "ref": folio_no, "value": f"Account {remitter_account} not registered, bank statement matches first holder"}],
                    "sop_clause": "6.2",
                    "human_approval_required": None
                }

    return {
        "check": "BANK_MANDATE",
        "result": "FAIL",
        "reason_codes": ["ACCOUNT_NOT_REGISTERED"],
        "proposed_outcome": "PEND",
        "evidence": [{"source": "bank_mandates", "ref": folio_no, "value": f"Account {remitter_account} not registered on folio"}],
        "sop_clause": "6.2",
        "human_approval_required": None
    }