"""KYC_STATUS check: validate KYC using KRA snapshot."""


def check_kyc(request: dict, extracted: dict, data: dict, resolved: dict) -> dict:
    kra_data = data.get("kra_kyc_snapshot", [])
    folio_master = data.get("folio_master", [])
    pan_masked = resolved.get("first_holder_pan_masked", "")

    if not pan_masked:
        return {
            "check": "KYC_STATUS",
            "result": "NOT_APPLICABLE",
            "reason_codes": ["NO_PAN_AVAILABLE"],
            "proposed_outcome": "PEND",
            "evidence": [],
            "sop_clause": "KYC",
            "human_approval_required": None
        }

    # Match KRA record by PAN
    kra_match = None
    for k in kra_data:
        kpan = k.get("pan_masked", "").strip()
        if kpan.replace("*", "").upper() == pan_masked.replace("*", "").upper():
            kra_match = k
            break

    if not kra_match:
        return {
            "check": "KYC_STATUS",
            "result": "UNABLE_TO_VERIFY",
            "reason_codes": ["KRA_RECORD_NOT_FOUND"],
            "proposed_outcome": "PEND",
            "evidence": [{"source": "kra_kyc_snapshot", "ref": pan_masked, "value": "PAN not found in KRA"}],
            "sop_clause": "KYC",
            "human_approval_required": "OPS_MANAGER"
        }

    status_code = kra_match.get("kra_status_code", "").strip()
    status_text = kra_match.get("kra_status", "").strip().upper()

    # Extract last 2 digits of status code for status value
    code_digits = status_code[-2:] if len(status_code) >= 2 else status_code.zfill(2)

    # Status mapping from last 2 digits
    status_map = {
        "07": "VALIDATED",
        "02": "REGISTERED",
        "03": "ON_HOLD",
        "04": "REJECTED",
        "01": "UNDER_PROCESS",
        "05": "NOT_AVAILABLE",
        "99": "UNREACHABLE"
    }

    kra_status = status_map.get(code_digits, status_text)

    # Check if it's a minor folio (need minor's KYC)
    folio_no = resolved.get("folio_no", "")
    folio_row = None
    for f in folio_master:
        if f.get("folio_no", "").strip() == folio_no:
            folio_row = f
            break

    if folio_row and folio_row.get("tax_status", "").strip() == "02 On behalf of minor":
        minor_pan = folio_row.get("first_holder_pan_masked", "")
        minor_kra = None
        for k in kra_data:
            if k.get("pan_masked", "").replace("*", "").upper() == minor_pan.replace("*", "").upper():
                minor_kra = k
                break
        if minor_kra:
            msc = minor_kra.get("kra_status_code", "").strip()
            msc_d = msc[-2:] if len(msc) >= 2 else msc.zfill(2)
            ms = status_map.get(msc_d, minor_kra.get("kra_status", "").strip().upper())
            if ms not in ("VALIDATED",):
                return {
                    "check": "KYC_STATUS",
                    "result": "FAIL",
                    "reason_codes": ["MINOR_KYC_NOT_VALIDATED", f"KRA_STATUS_{ms}"],
                    "proposed_outcome": "PEND",
                    "evidence": [{"source": "kra_kyc_snapshot", "ref": minor_pan, "value": f"Minor KYC: {ms}"}],
                    "sop_clause": "KYC",
                    "human_approval_required": None
                }
        return {
            "check": "KYC_STATUS",
            "result": "PASS",
            "reason_codes": ["MINOR_KYC_VALIDATED"],
            "proposed_outcome": "PROCEED",
            "evidence": [{"source": "kra_kyc_snapshot", "ref": minor_pan, "value": "Minor KYC Validated"}],
            "sop_clause": "KYC",
            "human_approval_required": None
        }

    if kra_status == "VALIDATED":
        return {
            "check": "KYC_STATUS",
            "result": "PASS",
            "reason_codes": ["KYC_VALIDATED"],
            "proposed_outcome": "PROCEED",
            "evidence": [{"source": "kra_kyc_snapshot", "ref": pan_masked, "value": f"KYC Validated ({kra_match.get('kra_name','')})"}],
            "sop_clause": "KYC",
            "human_approval_required": None
        }
    elif kra_status in ("REGISTERED",):
        if extracted.get("type") == "NEW_FOLIO_PURCHASE":
            # New AMC - PEND
            return {
                "check": "KYC_STATUS",
                "result": "FAIL",
                "reason_codes": ["KYC_REGISTERED_NEW_AMC_PEND"],
                "proposed_outcome": "PEND",
                "evidence": [{"source": "kra_kyc_snapshot", "ref": pan_masked, "value": f"KYC Registered - needs PEND for new AMC"}],
                "sop_clause": "KYC",
                "human_approval_required": None
            }
        # Same AMC - process with existing validated KYC
        return {
            "check": "KYC_STATUS",
            "result": "PASS",
            "reason_codes": ["KYC_REGISTERED_SAME_AMC"],
            "proposed_outcome": "PROCEED",
            "evidence": [{"source": "kra_kyc_snapshot", "ref": pan_masked, "value": "KYC Registered - same AMC"}],
            "sop_clause": "KYC",
            "human_approval_required": None
        }
    elif kra_status == "ON_HOLD":
        return {
            "check": "KYC_STATUS",
            "result": "FAIL",
            "reason_codes": ["KYC_ON_HOLD"],
            "proposed_outcome": "REJECT",
            "evidence": [{"source": "kra_kyc_snapshot", "ref": pan_masked, "value": "KYC On Hold"}],
            "sop_clause": "4.4",
            "human_approval_required": "CHECKER"
        }
    elif kra_status == "REJECTED":
        return {
            "check": "KYC_STATUS",
            "result": "FAIL",
            "reason_codes": ["KYC_REJECTED"],
            "proposed_outcome": "REJECT",
            "evidence": [{"source": "kra_kyc_snapshot", "ref": pan_masked, "value": "KYC Rejected"}],
            "sop_clause": "4.4",
            "human_approval_required": "CHECKER"
        }
    elif kra_status == "UNREACHABLE":
        return {
            "check": "KYC_STATUS",
            "result": "UNABLE_TO_VERIFY",
            "reason_codes": ["KRA_UNREACHABLE"],
            "proposed_outcome": "PEND",
            "evidence": [{"source": "kra_kyc_snapshot", "ref": pan_masked, "value": "KRA web service not reachable"}],
            "sop_clause": "KYC",
            "human_approval_required": "OPS_MANAGER"
        }
    else:
        return {
            "check": "KYC_STATUS",
            "result": "PASS",
            "reason_codes": ["KYC_UNDER_PROCESS"],
            "proposed_outcome": "PROCEED",
            "evidence": [{"source": "kra_kyc_snapshot", "ref": pan_masked, "value": f"KYC status: {kra_status}"}],
            "sop_clause": "KYC",
            "human_approval_required": None
        }