"""MINOR_RULES check (SOP 5.5): minor age verification and turned-18 logic."""

from datetime import datetime, date


def check_minor(request: dict, extracted: dict, data: dict, resolved: dict) -> dict:
    folio_master = data.get("folio_master", [])
    folio_no = resolved.get("folio_no", "")

    if not folio_no:
        return {
            "check": "MINOR_RULES",
            "result": "NOT_APPLICABLE",
            "reason_codes": ["NO_FOLIO"],
            "proposed_outcome": "PROCEED",
            "evidence": [],
            "sop_clause": "5.5",
            "human_approval_required": None
        }

    folio_row = None
    for f in folio_master:
        if f.get("folio_no", "").strip() == folio_no:
            folio_row = f
            break

    if not folio_row:
        return {
            "check": "MINOR_RULES",
            "result": "NOT_APPLICABLE",
            "reason_codes": ["FOLIO_NOT_FOUND"],
            "proposed_outcome": "PROCEED",
            "evidence": [],
            "sop_clause": "5.5",
            "human_approval_required": None
        }

    tax_status = (folio_row.get("tax_status", "") or "").strip()
    if tax_status != "02 On behalf of minor":
        return {
            "check": "MINOR_RULES",
            "result": "PASS",
            "reason_codes": ["NOT_A_MINOR_FOLIO"],
            "proposed_outcome": "PROCEED",
            "evidence": [{"source": "folio_master", "ref": folio_no, "value": f"Tax status: {tax_status}"}],
            "sop_clause": "5.5",
            "human_approval_required": None
        }

    minor_dob_str = (folio_row.get("minor_dob", "") or "").strip()
    if not minor_dob_str:
        return {
            "check": "MINOR_RULES",
            "result": "UNABLE_TO_VERIFY",
            "reason_codes": ["MINOR_DOB_MISSING"],
            "proposed_outcome": "PEND",
            "evidence": [{"source": "folio_master", "ref": folio_no, "value": "Minor DOB not available"}],
            "sop_clause": "5.5",
            "human_approval_required": "OPS_MANAGER"
        }

    try:
        minor_dob = datetime.strptime(minor_dob_str, "%Y-%m-%d").date()
    except ValueError:
        return {
            "check": "MINOR_RULES",
            "result": "UNABLE_TO_VERIFY",
            "reason_codes": ["MINOR_DOB_INVALID"],
            "proposed_outcome": "PEND",
            "evidence": [],
            "sop_clause": "5.5",
            "human_approval_required": "OPS_MANAGER"
        }

    received_at_str = request.get("received_at", "")
    try:
        received_dt = datetime.fromisoformat(received_at_str).date()
    except (ValueError, TypeError):
        received_dt = date.today()

    age = received_dt.year - minor_dob.year - ((received_dt.month, received_dt.day) < (minor_dob.month, minor_dob.day))
    guardian_relation = (folio_row.get("guardian_relation", "") or "").strip()

    if age >= 18:
        return {
            "check": "MINOR_RULES",
            "result": "FAIL",
            "reason_codes": ["MINOR_TURNED_18_PEND"],
            "proposed_outcome": "PEND",
            "evidence": [
                {"source": "folio_master", "ref": folio_no, "value": f"Minor DOB: {minor_dob_str}, Age: {age} (turned 18)"}
            ],
            "sop_clause": "5.5",
            "human_approval_required": None
        }

    return {
        "check": "MINOR_RULES",
        "result": "PASS",
        "reason_codes": ["MINOR_AGE_OK"],
        "proposed_outcome": "PROCEED",
        "evidence": [
            {"source": "folio_master", "ref": folio_no, "value": f"Minor DOB: {minor_dob_str}, Age: {age}, Guardian: {guardian_relation}"}
        ],
        "sop_clause": "5.5",
        "human_approval_required": None
    }