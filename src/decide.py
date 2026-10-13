"""Decision engine (SOP 9.2): determine final outcome from all check results.

SOP 9.2 order: INVALID_REQUEST > FAIL(REJECT) > HOLD_AND_REFER > PEND > PROCEED_MODIFIED > PROCEED.
Every FAIL and every non-PROCEED outcome MUST cite a SOP clause + evidence.

Approver per outcome:
  REJECT / PROCEED_MODIFIED  → CHECKER
  HOLD_AND_REFER             → OPS_MANAGER
  PROCEED                    → None
  PEND / INVALID_REQUEST     → None (flagged in human_approval_required by checks)
"""


def decide(check_results: list, overall: str, request_type: str) -> dict:
    fails = [r for r in check_results if r["result"] == "FAIL" and r.get("proposed_outcome") not in ("PROCEED_MODIFIED", "INVALID_REQUEST")]
    non_proceed = [r for r in check_results
                   if r["result"] not in ("NOT_APPLICABLE", "PASS") and r.get("proposed_outcome") not in ("PROCEED_MODIFIED", "INVALID_REQUEST")]

    for r in fails:
        assert r.get("sop_clause"), f"FAIL check {r['check']} missing sop_clause"
        assert r.get("evidence") is not None, f"FAIL check {r['check']} missing evidence"

    if overall not in ("PROCEED",):
        for r in non_proceed:
            assert r.get("sop_clause"), f"Non-proceed check {r['check']} missing sop_clause for outcome {overall}"
            assert r.get("evidence") is not None, f"Non-proceed check {r['check']} missing evidence for outcome {overall}"

    reason_codes = set()
    for r in check_results:
        for rc in r.get("reason_codes", []):
            reason_codes.add(rc)

    any_invalid = any(r.get("proposed_outcome") == "INVALID_REQUEST" for r in check_results)
    any_hold = any(r.get("proposed_outcome") == "HOLD_AND_REFER" for r in check_results)
    any_reject = any(r.get("proposed_outcome") == "REJECT" for r in check_results)
    any_modified = any(r.get("proposed_outcome") == "PROCEED_MODIFIED" for r in check_results)

    if any_invalid:
        final = "INVALID_REQUEST"
    elif any_reject:
        final = "REJECT"
    elif any_hold:
        final = "HOLD_AND_REFER"
    elif any(r.get("proposed_outcome") == "PEND" for r in check_results):
        final = "PEND"
    elif any(r["result"] == "UNABLE_TO_VERIFY" for r in check_results):
        final = "PEND"
    elif any_modified:
        final = "PROCEED_MODIFIED"
    elif all(r["result"] in ("PASS", "NOT_APPLICABLE") for r in check_results):
        final = "PROCEED"
    else:
        final = "PEND"

    if final in ("REJECT", "FAIL", "PROCEED_MODIFIED"):
        approver_role = "CHECKER"
    elif final == "HOLD_AND_REFER":
        approver_role = "OPS_MANAGER"
    elif final == "INVALID_REQUEST":
        approver_role = None
    else:
        approver_role = None

    return {
        "decision": final,
        "reason_code_summary": list(reason_codes),
        "approver_role": approver_role
    }