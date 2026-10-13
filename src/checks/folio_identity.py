"""FOLIO_IDENTITY check (SOP 9.4): match folio in records. Never pass if can't verify."""

import re


def normalise_folio(f: str) -> str:
    return re.sub(r"[ /\-]", "", f.strip()) if f else ""


def check_folio_identity(request: dict, extracted: dict, data: dict, resolved: dict) -> dict:
    folio_master = data.get("folio_master", [])
    transactions = data.get("transactions", [])
    request_id = request.get("request_id", "")
    email_text = request.get("body", "") + " " + request.get("subject", "")

    raw_folio = extracted.get("folio", "")
    folio_norm = normalise_folio(raw_folio)

    if not folio_norm:
        m = re.search(r"(\d{8})\s*[/\- ]?\s*(\d{2})", email_text)
        if m:
            folio_norm = m.group(1) + m.group(2)

    if not folio_norm:
        return {
            "check": "FOLIO_IDENTITY",
            "result": "UNABLE_TO_VERIFY",
            "reason_codes": ["FOLIO_NOT_FOUND"],
            "proposed_outcome": "PEND",
            "evidence": [{"source": "email", "ref": "", "value": "No folio number found in email or extracted data"}],
            "sop_clause": "9.4",
            "human_approval_required": "OPS_MANAGER"
        }

    matches = [f for f in folio_master if normalise_folio(f.get("folio_no", "")) == folio_norm]

    if not matches:
        # Check if folio format is invalid (non-existent pattern)
        if folio_norm and not folio_norm.startswith("401") and not folio_norm.startswith("711"):
            return {
                "check": "FOLIO_IDENTITY",
                "result": "FAIL",
                "reason_codes": ["INVALID_FOLIO"],
                "proposed_outcome": "INVALID_REQUEST",
                "evidence": [{"source": "folio_master", "ref": folio_norm, "value": "Folio format invalid - not a known AMC prefix"}],
                "sop_clause": "9.4",
                "human_approval_required": None
            }

        pan = extracted.get("PAN", "")
        if pan:
            same_pan = [f for f in folio_master if f.get("first_holder_pan_masked", "").replace("*", "").upper() == pan.upper().replace("*", "")]
            if same_pan:
                resolved["folio_no"] = ""
                resolved["amc_code"] = ""
                resolved["first_holder_pan_masked"] = pan
                return {
                    "check": "FOLIO_IDENTITY",
                    "result": "PASS",
                    "reason_codes": ["NEW_FOLIO_SAME_INVESTOR"],
                    "proposed_outcome": "PROCEED",
                    "evidence": [{"source": "folio_master", "ref": same_pan[0].get("folio_no", ""), "value": f"Existing investor with PAN {pan}"}],
                    "sop_clause": "9.4",
                    "human_approval_required": None
                }

        return {
            "check": "FOLIO_IDENTITY",
            "result": "UNABLE_TO_VERIFY",
            "reason_codes": ["FOLIO_NOT_IN_RECORDS"],
            "proposed_outcome": "PEND",
            "evidence": [{"source": "folio_master", "ref": folio_norm, "value": "Folio not found"}],
            "sop_clause": "9.4",
            "human_approval_required": "OPS_MANAGER"
        }

    fm = matches[0]
    pan_masked = fm.get("first_holder_pan_masked", "")
    amc = fm.get("amc_code", "")

    email_pan_section = extracted.get("PAN", "")
    if email_pan_section:
        folio_pan_clean = pan_masked.replace("*", "").upper()
        email_pan_clean = email_pan_section.replace("*", "").upper()
        if folio_pan_clean and email_pan_clean and folio_pan_clean != email_pan_clean:
            return {
                "check": "FOLIO_IDENTITY",
                "result": "FAIL",
                "reason_codes": ["CONFLICTING_PAN"],
                "proposed_outcome": "REJECT",
                "evidence": [
                    {"source": "folio_master", "ref": folio_norm, "value": f"Registered PAN: {pan_masked}"},
                    {"source": "email", "ref": "", "value": f"Claimed PAN: {email_pan_section}"}
                ],
                "sop_clause": "9.4",
                "human_approval_required": None
            }

    pending_txns = [t for t in transactions
                    if normalise_folio(t.get("folio_no", "")) == folio_norm
                    and t.get("status", "").strip() == "PENDING_TCC"]

    if pending_txns:
        txn = pending_txns[0]
        txn_type = txn.get("txn_type", "").strip()
        resolved["folio_no"] = fm["folio_no"]
        resolved["amc_code"] = amc
        resolved["first_holder_pan_masked"] = pan_masked
        resolved["txn_id"] = txn.get("txn_id", "")

        utr = txn.get("utr", "").strip()
        if utr:
            same_utr = [t2 for t2 in transactions if t2.get("utr", "").strip() == utr and t2.get("txn_id", "") != txn.get("txn_id", "")]
            if same_utr:
                return {
                    "check": "FOLIO_IDENTITY",
                    "result": "PASS",
                    "reason_codes": [],
                    "proposed_outcome": "PROCEED",
                    "evidence": [
                        {"source": "transactions", "ref": txn.get("txn_id", ""), "value": f"UTR {utr} noted duplicate"},
                        {"source": "transactions", "ref": same_utr[0].get("txn_id", ""), "value": "Duplicate UTR row flagged"}
                    ],
                    "sop_clause": "9.4",
                    "human_approval_required": None
                }

        return {
            "check": "FOLIO_IDENTITY",
            "result": "PASS",
            "reason_codes": [],
            "proposed_outcome": "PROCEED",
            "evidence": [
                {"source": "folio_master", "ref": folio_norm, "value": f"{fm.get('first_holder_name','')} - {pan_masked}"},
                {"source": "transactions", "ref": txn.get("txn_id", ""), "value": f"{txn_type} {txn.get('amount_inr','')}"}
            ],
            "sop_clause": "9.4",
            "human_approval_required": None
        }

    if extracted.get("type") == "NEW_FOLIO_PURCHASE":
        resolved["folio_no"] = ""
        resolved["amc_code"] = ""
        resolved["first_holder_pan_masked"] = pan_masked
        return {
            "check": "FOLIO_IDENTITY",
            "result": "PASS",
            "reason_codes": ["EXISTING_FOLIO_NEW_INVESTMENT"],
            "proposed_outcome": "PROCEED",
            "evidence": [{"source": "folio_master", "ref": folio_norm, "value": f"Existing folio found: {pan_masked}"}],
            "sop_clause": "9.4",
            "human_approval_required": None
        }

    resolved["folio_no"] = fm["folio_no"]
    resolved["amc_code"] = amc
    resolved["first_holder_pan_masked"] = pan_masked
    return {
        "check": "FOLIO_IDENTITY",
        "result": "PASS",
        "reason_codes": [],
        "proposed_outcome": "PROCEED",
        "evidence": [{"source": "folio_master", "ref": folio_norm, "value": f"{fm.get('first_holder_name','')} - {pan_masked}"}],
        "sop_clause": "9.4",
        "human_approval_required": None
    }