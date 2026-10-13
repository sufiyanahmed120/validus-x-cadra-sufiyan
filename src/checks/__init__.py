"""Check engine: run all 8 check_ids and aggregate results.

Required check_ids (all 8 always in output, NOT_APPLICABLE if unused):
  FOLIO_IDENTITY, KYC_STATUS, THIRD_PARTY_PAYMENT, BANK_MANDATE,
  COB_COOLING, DISTRIBUTOR_CODE, MINOR_RULES, REFERRAL
"""

from typing import Any
from src.checks.folio_identity import check_folio_identity
from src.checks.kyc import check_kyc
from src.checks.third_party import check_third_party
from src.checks.bank import check_bank
from src.checks.cob import check_cob
from src.checks.distributor import check_distributor
from src.checks.minor import check_minor
from src.checks.referral import check_referral

CHECKS_REGISTRY = [  # exactly 8 check_ids as required
    ("FOLIO_IDENTITY", check_folio_identity),
    ("KYC_STATUS", check_kyc),
    ("THIRD_PARTY_PAYMENT", check_third_party),
    ("BANK_MANDATE", check_bank),
    ("COB_COOLING", check_cob),
    ("DISTRIBUTOR_CODE", check_distributor),
    ("MINOR_RULES", check_minor),
    ("REFERRAL", check_referral),
]


def run_all_checks(request: dict, extracted: dict, data: dict) -> tuple[list, dict]:
    results = []
    human_approval = None
    resolved = {
        "folio_no": "",
        "amc_code": "",
        "first_holder_pan_masked": "",
        "txn_id": ""
    }

    for name, fn in CHECKS_REGISTRY:
        try:
            r = fn(request, extracted, data, resolved)
            results.append(r)
        except Exception as e:
            results.append({
                "check": name,
                "result": "UNABLE_TO_VERIFY",
                "reason_codes": [f"CHECK_ERROR: {str(e)}"],
                "proposed_outcome": "PEND",
                "evidence": [],
                "sop_clause": "",
                "human_approval_required": "OPS_MANAGER"
            })

    any_unable = any(r["result"] == "UNABLE_TO_VERIFY" for r in results)
    any_modified = any(r.get("proposed_outcome") == "PROCEED_MODIFIED" for r in results)
    any_fail = any(r["result"] == "FAIL" and r.get("proposed_outcome") != "PROCEED_MODIFIED" for r in results)

    # SOP 9.2 order: INVALID_REQUEST > REJECT > HOLD_AND_REFER > PEND > PROCEED_MODIFIED > PROCEED
    has_invalid = any(r.get("proposed_outcome") == "INVALID_REQUEST" for r in results) or any("INVALID" in " ".join(r.get("reason_codes", [])).upper() for r in results)
    has_reject = any(r.get("proposed_outcome") == "REJECT" for r in results)
    has_hold = any(r.get("proposed_outcome") == "HOLD_AND_REFER" for r in results)
    has_pend = any(r.get("proposed_outcome") == "PEND" for r in results)

    if has_invalid:
        overall = "INVALID_REQUEST"
    elif has_reject or any_fail:
        overall = "FAIL"
    elif has_hold:
        overall = "HOLD_AND_REFER"
    elif has_pend or any_unable:
        overall = "PEND"
    elif any_modified:
        overall = "PROCEED_MODIFIED"
    elif all(r["result"] in ("PASS", "NOT_APPLICABLE") for r in results):
        overall = "PROCEED"
    else:
        overall = "PEND"

    for r in results:
        ha = r.get("human_approval_required")
        if ha:
            human_approval = ha

    evidence_flat = [{"source": e["source"], "ref": e.get("ref", ""), "value": e.get("value", "")}
                     for r in results for e in r.get("evidence", [])]

    for r in results:
        if r["result"] not in ("NOT_APPLICABLE", "PASS"):
            human_approval = human_approval or "CHECKER"

    return results, overall, human_approval, resolved, evidence_flat