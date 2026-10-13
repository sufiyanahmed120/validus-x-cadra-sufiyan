"""Response contract enforcement (SOP 9.1-9.3).

Exact contract names:
  - top-level per-request outcome field is "outcomes" (NOT "decision")
  - each check item uses "check_id" (NOT "check")

Value domains:
  - outcomes / proposed_outcome: the six SOP 9.1 outcomes only
  - reason_codes: the SOP 9.3 codes only
  - folio_no: canonical "NNNNNNNN/NN" form
"""

import re

OUTCOMES = (
    "PROCEED",
    "PROCEED_MODIFIED",
    "PEND",
    "REJECT",
    "HOLD_AND_REFER",
    "INVALID_REQUEST",
)

SOP_REASON_CODES = {
    "KYC_ON_HOLD",
    "KYC_REJECTED",
    "KYC_REGISTERED_NEW_AMC",
    "KYC_UNABLE_TO_VERIFY",
    "TPP_NO_EXCEPTION",
    "TPP_DOCS_MISSING",
    "BANK_PROOF_REQUIRED",
    "MINOR_ATTAINED_MAJORITY",
    "COB_COOLING",
    "HIGH_RISK_CONTACT_COB",
    "ARN_INVALID_DIRECT",
    "EUIN_MISSING",
    "REFERRAL_TRIGGER",
    "STOP_LOCK",
    "CASH_LIMIT_BREACH",
    "FOLIO_NOT_FOUND",
    "FOLIO_PAN_MISMATCH",
}

_EXACT_CODE_MAP = {
    ("FOLIO_IDENTITY", "INVALID_FOLIO"): "FOLIO_NOT_FOUND",
    ("FOLIO_IDENTITY", "FOLIO_NOT_IN_RECORDS"): "FOLIO_NOT_FOUND",
    ("FOLIO_IDENTITY", "FOLIO_NOT_FOUND"): "FOLIO_NOT_FOUND",
    ("FOLIO_IDENTITY", "CONFLICTING_PAN"): "FOLIO_PAN_MISMATCH",
    ("KYC_STATUS", "KYC_ON_HOLD"): "KYC_ON_HOLD",
    ("KYC_STATUS", "KYC_REJECTED"): "KYC_REJECTED",
    ("KYC_STATUS", "KYC_REGISTERED_NEW_AMC_PEND"): "KYC_REGISTERED_NEW_AMC",
    ("KYC_STATUS", "KRA_UNREACHABLE"): "KYC_UNABLE_TO_VERIFY",
    ("KYC_STATUS", "KRA_RECORD_NOT_FOUND"): "KYC_UNABLE_TO_VERIFY",
    ("KYC_STATUS", "MINOR_KYC_NOT_VALIDATED"): "KYC_UNABLE_TO_VERIFY",
    ("THIRD_PARTY_PAYMENT", "THIRD_PARTY_GRANDPARENT_REJECT"): "TPP_NO_EXCEPTION",
    ("THIRD_PARTY_PAYMENT", "THIRD_PARTY_UNRELATED"): "TPP_NO_EXCEPTION",
    ("THIRD_PARTY_PAYMENT", "EMPLOYER_DOCS_MISSING_PEND"): "TPP_DOCS_MISSING",
    ("THIRD_PARTY_PAYMENT", "OWN_UNREGISTERED_NO_STATEMENT"): "TPP_DOCS_MISSING",
    ("THIRD_PARTY_PAYMENT", "FOLIO_NOT_FOUND"): "FOLIO_NOT_FOUND",
    ("BANK_MANDATE", "ACCOUNT_NOT_REGISTERED"): "BANK_PROOF_REQUIRED",
    ("BANK_MANDATE", "ACCOUNT_PENDING_VALIDATION"): "BANK_PROOF_REQUIRED",
    ("BANK_MANDATE", "ACCOUNT_ON_OTHER_FOLIO"): "BANK_PROOF_REQUIRED",
    ("BANK_MANDATE", "ACCOUNT_REJECTED"): "BANK_PROOF_REQUIRED",
    ("BANK_MANDATE", "TXN_NOT_FOUND"): "BANK_PROOF_REQUIRED",
    ("COB_COOLING", "COB_COOLING"): "COB_COOLING",
    ("COB_COOLING", "HIGH_RISK_CONTACT_COB"): "HIGH_RISK_CONTACT_COB",
    ("DISTRIBUTOR_CODE", "ARN_EXPIRED"): "ARN_INVALID_DIRECT",
    ("DISTRIBUTOR_CODE", "ARN_CANCELLED"): "ARN_INVALID_DIRECT",
    ("DISTRIBUTOR_CODE", "ARN_SUSPENDED"): "ARN_INVALID_DIRECT",
    ("DISTRIBUTOR_CODE", "ARN_NOT_FOUND"): "ARN_INVALID_DIRECT",
    ("DISTRIBUTOR_CODE", "ARN_NOT_EMPANELLED_NMF"): "ARN_INVALID_DIRECT",
    ("DISTRIBUTOR_CODE", "ARN_NOT_EMPANELLED_TMF"): "ARN_INVALID_DIRECT",
    ("DISTRIBUTOR_CODE", "EUIN_NOT_FOUND"): "EUIN_MISSING",
    ("MINOR_RULES", "MINOR_TURNED_18_PEND"): "MINOR_ATTAINED_MAJORITY",
    ("REFERRAL", "STOP_LOCK_ACTIVE"): "STOP_LOCK",
    ("REFERRAL", "CASH_EXCEEDS_50K"): "CASH_LIMIT_BREACH",
    ("REFERRAL", "TMF_A1_REDEMPTION_WITHIN_30D"): "REFERRAL_TRIGGER",
    ("REFERRAL", "TMF_A2_SOP_VERSION_MISSING"): "REFERRAL_TRIGGER",
}

_OUTCOME_ALIASES = {
    "PROCESS": "PROCEED",
    "PEND_COB": "PEND",
    "FAIL": "REJECT",
    "PASS": "PROCEED",
    "OK": "PROCEED",
}


def format_folio(folio: str) -> str:
    """Return folio in canonical NNNNNNNN/NN form when digits-only."""
    if not folio:
        return ""
    f = str(folio).strip()
    m = re.fullmatch(r"(\d{8})(\d{2})", f)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    return f


def _to_outcome(value: str, result: str) -> str:
    v = (value or "").strip().upper()
    if v in OUTCOMES:
        return v
    if v in _OUTCOME_ALIASES:
        return _OUTCOME_ALIASES[v]
    return "PROCEED" if result in ("PASS", "NOT_APPLICABLE") else "PEND"


def _to_reason_codes(check_id: str, codes: list, result: str) -> list:
    if result in ("PASS", "NOT_APPLICABLE"):
        return []
    out = []
    for code in codes or []:
        c = (code or "").strip()
        if c in SOP_REASON_CODES:
            mapped = c
        elif c.startswith("KRA_STATUS_"):
            mapped = "KYC_UNABLE_TO_VERIFY"
        else:
            mapped = _EXACT_CODE_MAP.get((check_id, c))
        if mapped and mapped not in out:
            out.append(mapped)
    return out


def normalize_check(check: dict) -> dict:
    """Rewrite one check item to the contract shape."""
    check_id = check.get("check_id", check.get("check", ""))
    result = check.get("result", "")
    proposed = _to_outcome(check.get("proposed_outcome", ""), result)
    return {
        "check_id": check_id,
        "result": result,
        "reason_codes": _to_reason_codes(check_id, check.get("reason_codes", []), result),
        "proposed_outcome": proposed,
        "evidence": check.get("evidence", []),
        "sop_clause": check.get("sop_clause", ""),
    }


def normalize_response(resp: dict) -> dict:
    """Return a copy of the response using exact contract names and domains."""
    out = dict(resp)
    out["outcomes"] = _to_outcome(resp.get("outcomes", resp.get("decision", "")), "")
    out.pop("decision", None)
    out.pop("chase_results", None)

    # human_approval_required is a boolean; approver_role is a separate top-level field.
    har = resp.get("human_approval_required")
    if isinstance(har, dict):
        out["human_approval_required"] = bool(har.get("required"))
        if out.get("approver_role") is None:
            out["approver_role"] = har.get("approver_role")
    else:
        out["human_approval_required"] = bool(har)

    if out.get("approver_role") not in ("CHECKER", "OPS_MANAGER"):
        out["approver_role"] = None

    resolved = dict(resp.get("resolved", {}))
    if resolved:
        resolved["folio_no"] = format_folio(resolved.get("folio_no", ""))
    out["resolved"] = resolved

    out["checks"] = [normalize_check(c) for c in resp.get("checks", [])]

    seen = []
    for c in out["checks"]:
        for code in c["reason_codes"]:
            if code not in seen:
                seen.append(code)
    out["reason_codes"] = seen

    trace = dict(resp.get("trace", {}))
    trace["tools_called"] = [c["check_id"] for c in out["checks"]]
    out["trace"] = trace

    return out


def validate_response(resp: dict) -> list:
    """Return a list of contract violations (empty when compliant)."""
    errors = []

    if "decision" in resp:
        errors.append("top-level 'decision' present; must be 'outcomes'")
    if "outcomes" not in resp:
        errors.append("missing top-level 'outcomes'")
    elif resp["outcomes"] not in OUTCOMES:
        errors.append(f"outcomes value '{resp['outcomes']}' is not one of the six outcomes")

    if not isinstance(resp.get("human_approval_required"), bool):
        errors.append("human_approval_required must be a boolean")
    if resp.get("approver_role") not in ("CHECKER", "OPS_MANAGER", None):
        errors.append(f"approver_role '{resp.get('approver_role')}' must be CHECKER, OPS_MANAGER or null")

    for code in resp.get("reason_codes", []):
        if code not in SOP_REASON_CODES:
            errors.append(f"top-level reason_code '{code}' is not a SOP 9.3 code")

    if "checks" not in resp or not isinstance(resp["checks"], list):
        errors.append("missing 'checks' list")
        return errors

    for i, c in enumerate(resp["checks"]):
        if "check" in c and "check_id" not in c:
            errors.append(f"checks[{i}] uses 'check'; must be 'check_id'")
        if "check_id" not in c:
            errors.append(f"checks[{i}] missing 'check_id'")
        if c.get("proposed_outcome") not in OUTCOMES:
            errors.append(f"checks[{i}] proposed_outcome '{c.get('proposed_outcome')}' not in the six outcomes")
        for code in c.get("reason_codes", []):
            if code not in SOP_REASON_CODES:
                errors.append(f"checks[{i}] reason_code '{code}' is not a SOP 9.3 code")

    folio = (resp.get("resolved") or {}).get("folio_no", "")
    if folio and not re.fullmatch(r"\d{8}/\d{2}", folio):
        errors.append(f"resolved.folio_no '{folio}' not in NNNNNNNN/NN format")

    return errors
