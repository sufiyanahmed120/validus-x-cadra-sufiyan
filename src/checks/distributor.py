"""DISTRIBUTOR_CODE check: validate ARN/EUIN status and empanelment."""

from datetime import datetime


def check_distributor(request: dict, extracted: dict, data: dict, resolved: dict) -> dict:
    dist_data = data.get("distributor_master", [])
    folio_master = data.get("folio_master", [])
    transactions = data.get("transactions", [])

    folio_no = resolved.get("folio_no", "")
    txn_id = resolved.get("txn_id", "")

    txn = None
    for t in transactions:
        if t.get("txn_id", "").strip() == txn_id:
            txn = t
            break

    if not txn:
        return {
            "check": "DISTRIBUTOR_CODE",
            "result": "NOT_APPLICABLE",
            "reason_codes": ["NO_TXN"],
            "proposed_outcome": "PROCEED",
            "evidence": [],
            "sop_clause": "DISTRIBUTOR",
            "human_approval_required": None
        }

    arn = (txn.get("arn", "") or "").strip()
    euin = (txn.get("euin", "") or "").strip()

    if not arn and not euin:
        return {
            "check": "DISTRIBUTOR_CODE",
            "result": "PASS",
            "reason_codes": ["DIRECT_PLAN"],
            "proposed_outcome": "PROCEED",
            "evidence": [{"source": "transactions", "ref": txn_id, "value": "No ARN/EUIN - Direct plan"}],
            "sop_clause": "DISTRIBUTOR",
            "human_approval_required": None
        }

    # Look up ARN in distributor master
    arn_row = None
    for d in dist_data:
        if (d.get("arn", "") or "").strip().upper() == arn.upper():
            arn_row = d
            break

    if not arn_row:
        return {
            "check": "DISTRIBUTOR_CODE",
            "result": "FAIL",
            "reason_codes": ["ARN_NOT_FOUND"],
            "proposed_outcome": "PEND",
            "evidence": [{"source": "distributor_master", "ref": arn, "value": "ARN not found in distributor master"}],
            "sop_clause": "DISTRIBUTOR",
            "human_approval_required": None
        }

    arn_status = (arn_row.get("arn_status", "") or "").strip().upper()
    arn_valid_till_str = (arn_row.get("arn_valid_till", "") or "").strip()

    folio_amc = resolved.get("amc_code", "")
    # Check ARN status
    if arn_status == "EXPIRED":
        proposed_outcome = "PROCEED_MODIFIED" if folio_amc else "PEND"
        return {
            "check": "DISTRIBUTOR_CODE",
            "result": "FAIL",
            "reason_codes": ["ARN_EXPIRED"],
            "proposed_outcome": proposed_outcome,
            "evidence": [{"source": "distributor_master", "ref": arn, "value": f"ARN {arn} EXPIRED, valid till {arn_valid_till_str}"}],
            "sop_clause": "DISTRIBUTOR",
            "human_approval_required": None
        }

    if arn_status == "SUSPENDED":
        return {
            "check": "DISTRIBUTOR_CODE",
            "result": "FAIL",
            "reason_codes": ["ARN_SUSPENDED"],
            "proposed_outcome": "PEND",
            "evidence": [{"source": "distributor_master", "ref": arn, "value": f"ARN {arn} SUSPENDED"}],
            "sop_clause": "DISTRIBUTOR",
            "human_approval_required": None
        }

    if arn_status == "CANCELLED":
        return {
            "check": "DISTRIBUTOR_CODE",
            "result": "FAIL",
            "reason_codes": ["ARN_CANCELLED"],
            "proposed_outcome": "REJECT",
            "evidence": [{"source": "distributor_master", "ref": arn, "value": f"ARN {arn} CANCELLED"}],
            "sop_clause": "DISTRIBUTOR",
            "human_approval_required": None
        }

    # Check EUIN if present
    if euin:
        euin_match = None
        for d in dist_data:
            if (d.get("euin", "") or "").strip().upper() == euin.upper():
                euin_match = d
                break
        if not euin_match:
            return {
                "check": "DISTRIBUTOR_CODE",
                "result": "FAIL",
                "reason_codes": ["EUIN_NOT_FOUND"],
                "proposed_outcome": "PEND",
                "evidence": [{"source": "distributor_master", "ref": euin, "value": "EUIN not found"}],
                "sop_clause": "DISTRIBUTOR",
                "human_approval_required": None
            }

    # Check empanelment
    if folio_amc == "NMF":
        emp = (arn_row.get("empanelled_nmf", "") or "").strip()
        if emp and emp.upper() != "Y":
            return {
                "check": "DISTRIBUTOR_CODE",
                "result": "FAIL",
                "reason_codes": ["ARN_NOT_EMPANELLED_NMF"],
                "proposed_outcome": "PEND",
                "evidence": [{"source": "distributor_master", "ref": arn, "value": f"ARN {arn} not empanelled with NMF"}],
                "sop_clause": "DISTRIBUTOR",
                "human_approval_required": None
            }
    elif folio_amc == "TMF":
        emp = (arn_row.get("empanelled_tmf", "") or "").strip()
        if emp and emp.upper() != "Y":
            return {
                "check": "DISTRIBUTOR_CODE",
                "result": "FAIL",
                "reason_codes": ["ARN_NOT_EMPANELLED_TMF"],
                "proposed_outcome": "PEND",
                "evidence": [{"source": "distributor_master", "ref": arn, "value": f"ARN {arn} not empanelled with TMF"}],
                "sop_clause": "DISTRIBUTOR",
                "human_approval_required": None
            }

    return {
        "check": "DISTRIBUTOR_CODE",
        "result": "PASS",
        "reason_codes": ["ARN_ACTIVE_EMPANELLED"],
        "proposed_outcome": "PROCEED",
        "evidence": [{"source": "distributor_master", "ref": arn, "value": f"ARN {arn} ACTIVE, empanelled"}],
        "sop_clause": "DISTRIBUTOR",
        "human_approval_required": None
    }