"""THIRD_PARTY_PAYMENT check: first holder must hold the paying account."""

import re


def get_account_last4(account_str: str) -> str:
    if not account_str:
        return ""
    digits = re.sub(r"\D", "", account_str)
    return digits[-4:] if len(digits) >= 4 else digits


def check_third_party(request: dict, extracted: dict, data: dict, resolved: dict) -> dict:
    bank_mandates = data.get("bank_mandates", [])
    folio_master = data.get("folio_master", [])
    transactions = data.get("transactions", [])

    folio_no = resolved.get("folio_no", "")
    txn_id = resolved.get("txn_id", "")

    if not txn_id:
        return {
            "check": "THIRD_PARTY_PAYMENT",
            "result": "NOT_APPLICABLE",
            "reason_codes": ["NO_TXN"],
            "proposed_outcome": "PROCEED",
            "evidence": [],
            "sop_clause": "THIRD_PARTY",
            "human_approval_required": None
        }

    txn = None
    for t in transactions:
        if t.get("txn_id", "").strip() == txn_id:
            txn = t
            break

    if not txn:
        return {
            "check": "THIRD_PARTY_PAYMENT",
            "result": "UNABLE_TO_VERIFY",
            "reason_codes": ["TXN_NOT_FOUND"],
            "proposed_outcome": "PEND",
            "evidence": [],
            "sop_clause": "THIRD_PARTY",
            "human_approval_required": "OPS_MANAGER"
        }

    # A redemption/switch-out is an outgoing payout: there is no incoming payment,
    # so third-party payment rules (SOP 5) do not apply.
    if (txn.get("txn_type", "") or "").strip() in ("RED", "SWO"):
        return {
            "check": "THIRD_PARTY_PAYMENT",
            "result": "NOT_APPLICABLE",
            "reason_codes": [],
            "proposed_outcome": "PROCEED",
            "evidence": [{"source": "transactions", "ref": txn_id, "value": "Redemption - no incoming payment"}],
            "sop_clause": "5",
            "human_approval_required": None
        }

    remitter_name = (txn.get("remitter_name", "") or "").strip()
    remitter_account = (txn.get("remitter_account_masked", "") or "").strip()
    payment_mode = (txn.get("payment_mode", "") or "").strip()

    if payment_mode in ("NACH", "CHEQUE", "CASH"):
        return {
            "check": "THIRD_PARTY_PAYMENT",
            "result": "PASS",
            "reason_codes": [f"PAYMENT_MODE_{payment_mode}"],
            "proposed_outcome": "PROCEED",
            "evidence": [{"source": "transactions", "ref": txn_id, "value": f"Mode: {payment_mode}"}],
            "sop_clause": "THIRD_PARTY",
            "human_approval_required": None
        }

    # Get first holder name
    folio_row = None
    for f in folio_master:
        if f.get("folio_no", "").strip() == folio_no:
            folio_row = f
            break

    if not folio_row:
        return {
            "check": "THIRD_PARTY_PAYMENT",
            "result": "UNABLE_TO_VERIFY",
            "reason_codes": ["FOLIO_NOT_FOUND"],
            "proposed_outcome": "PEND",
            "evidence": [],
            "sop_clause": "THIRD_PARTY",
            "human_approval_required": "OPS_MANAGER"
        }

    first_holder = (folio_row.get("first_holder_name", "") or "").strip().upper()
    tax_status = (folio_row.get("tax_status", "") or "").strip()

    # Check if remitter name matches first holder (partial)
    remitter_upper = remitter_name.upper()
    first_parts = set(first_holder.replace(".", "").split())
    remit_parts = set(remitter_upper.replace(".", "").split())

    name_match = len(first_parts & remit_parts) > 0

    # Check if remitter is the second holder (joint/AS folio)
    second_holder = (folio_row.get("second_holder_name", "") or "").strip().upper()
    second_match = False
    if second_holder:
        second_parts = set(second_holder.replace(".", "").split())
        second_match = len(second_parts & remit_parts) >= min(len(second_parts), 2)

    # Check if remitter account is registered on the folio
    folio_banks = [b for b in bank_mandates if b.get("folio_no", "").strip() == folio_no]
    account_match = False
    for b in folio_banks:
        ba = (b.get("account_no_masked", "") or "").strip()
        if ba and remitter_account and get_account_last4(ba) == get_account_last4(remitter_account):
            if b.get("status", "").strip() == "VALIDATED":
                account_match = True
                break

    if name_match and account_match:
        return {
            "check": "THIRD_PARTY_PAYMENT",
            "result": "PASS",
            "reason_codes": ["SELF_PAYMENT_MATCHED"],
            "proposed_outcome": "PROCEED",
            "evidence": [
                {"source": "folio_master", "ref": folio_no, "value": f"First holder: {first_holder}"},
                {"source": "bank_mandates", "ref": folio_no, "value": f"Account matched: {remitter_account}"}
            ],
            "sop_clause": "THIRD_PARTY",
            "human_approval_required": None
        }

    # Second holder paying on joint/AS folio - always allowed
    holding_mode = (folio_row.get("holding_mode", "") or "").strip()
    if second_match and holding_mode in ("JO", "AS"):
        return {
            "check": "THIRD_PARTY_PAYMENT",
            "result": "PASS",
            "reason_codes": ["SECOND_HOLDER_PAYMENT"],
            "proposed_outcome": "PROCEED",
            "evidence": [
                {"source": "folio_master", "ref": folio_no, "value": f"Second holder: {second_holder}"},
                {"source": "transactions", "ref": txn_id, "value": f"Remitter: {remitter_name}"}
            ],
            "sop_clause": "THIRD_PARTY",
            "human_approval_required": None
        }

    # Check minor relationship
    is_minor = tax_status == "02 On behalf of minor"
    guardian_name = (folio_row.get("guardian_name", "") or "").strip().upper()
    guardian_relation = (folio_row.get("guardian_relation", "") or "").strip()

    if is_minor:
        remitter_upper = remitter_name.upper()
        guardian_upper = guardian_name.upper()
        g_first = guardian_upper.replace(".", "").split()[0] if guardian_upper.replace(".", "").split() else ""
        r_first = remitter_upper.replace(".", "").split()[0] if remitter_upper.replace(".", "").split() else ""
        is_guardian = (g_first == r_first) and g_first != ""

        if is_guardian:
            if guardian_relation == "FATHER" or guardian_relation == "MOTHER":
                return {
                    "check": "THIRD_PARTY_PAYMENT",
                    "result": "PASS",
                    "reason_codes": [f"MINOR_GUARDIAN_{guardian_relation}"],
                    "proposed_outcome": "PROCEED",
                    "evidence": [
                        {"source": "folio_master", "ref": folio_no, "value": f"Minor folio. Guardian: {guardian_name} ({guardian_relation})"},
                        {"source": "transactions", "ref": txn_id, "value": f"Remitter: {remitter_name}"}
                    ],
                    "sop_clause": "THIRD_PARTY",
                    "human_approval_required": None
                }

        # Check for grandparent (REJECT in v4.1)
        # Grandparent detection: remitter different from guardian and not the first holder
        if not is_guardian:
            # Check if remitter is really the first holder (parent investing for own minor child)
            guardian_parts = set(guardian_upper.replace(".", "").split())
            is_parent_investor = len(guardian_parts & remit_parts) >= min(len(guardian_parts), 2)
            if not is_parent_investor:
                # On a minor folio, if remitter is not the guardian, it's a third party (grandparent)
                return {
                    "check": "THIRD_PARTY_PAYMENT",
                    "result": "FAIL",
                    "reason_codes": ["THIRD_PARTY_GRANDPARENT_REJECT"],
                    "proposed_outcome": "REJECT",
                    "evidence": [
                        {"source": "folio_master", "ref": folio_no, "value": f"Minor folio. Guardian: {guardian_name} ({guardian_relation})"},
                        {"source": "transactions", "ref": txn_id, "value": f"Remitter not guardian: {remitter_name}"}
                    ],
                    "sop_clause": "v4.1 Minor/THIRD_PARTY",
                    "human_approval_required": None
                }

    # Employer payment check
    email_text = request.get("body", "") + " " + request.get("subject", "")
    is_employer = any(kw in email_text.upper() for kw in ["EMPLOYEE", "PAYROLL", "EMPLOYER", "HR"])

    if is_employer:
        # Check all documents attached
        attachments = request.get("attachments", [])
        if len(attachments) >= 2:
            return {
                "check": "THIRD_PARTY_PAYMENT",
                "result": "PASS",
                "reason_codes": ["EMPLOYER_PAYMENT_DOCS_ATTACHED"],
                "proposed_outcome": "PROCEED",
                "evidence": [
                    {"source": "email", "ref": "", "value": f"Employer payment. {len(attachments)} docs attached"},
                    {"source": "transactions", "ref": txn_id, "value": f"Remitter: {remitter_name}"}
                ],
                "sop_clause": "THIRD_PARTY",
                "human_approval_required": None
            }
        return {
            "check": "THIRD_PARTY_PAYMENT",
            "result": "FAIL",
            "reason_codes": ["EMPLOYER_DOCS_MISSING_PEND"],
            "proposed_outcome": "PEND",
            "evidence": [
                {"source": "email", "ref": "", "value": f"Employer payment but only {len(attachments)} docs attached"}
            ],
            "sop_clause": "THIRD_PARTY",
            "human_approval_required": None
        }

    # Own unregistered account - need statement showing debit
    if not account_match and name_match:
        attachments = request.get("attachments", [])
        has_statement = any("STATEMENT" in (a.get("file_name", "") or "").upper() or "EXTRACT" in (a.get("file_name", "") or "").upper() for a in attachments)
        if has_statement:
            return {
                "check": "THIRD_PARTY_PAYMENT",
                "result": "PASS",
                "reason_codes": ["OWN_UNREGISTERED_ACCOUNT_WITH_STATEMENT"],
                "proposed_outcome": "PROCEED",
                "evidence": [
                    {"source": "bank_mandates", "ref": folio_no, "value": f"Account {remitter_account} not registered, but statement attached"},
                    {"source": "transactions", "ref": txn_id, "value": f"Remitter: {remitter_name}"}
                ],
                "sop_clause": "THIRD_PARTY",
                "human_approval_required": None
            }
        return {
            "check": "THIRD_PARTY_PAYMENT",
            "result": "FAIL",
            "reason_codes": ["OWN_UNREGISTERED_NO_STATEMENT"],
            "proposed_outcome": "PEND",
            "evidence": [{"source": "bank_mandates", "ref": folio_no, "value": f"Account {remitter_account} not registered, no statement"}],
            "sop_clause": "THIRD_PARTY",
            "human_approval_required": None
        }

    # Third party payment from someone unrelated
    return {
        "check": "THIRD_PARTY_PAYMENT",
        "result": "FAIL",
        "reason_codes": ["THIRD_PARTY_UNRELATED"],
        "proposed_outcome": "PEND",
        "evidence": [
            {"source": "folio_master", "ref": folio_no, "value": f"First holder: {first_holder}"},
            {"source": "transactions", "ref": txn_id, "value": f"Remitter: {remitter_name} / {remitter_account}"}
        ],
        "sop_clause": "THIRD_PARTY",
        "human_approval_required": None
    }