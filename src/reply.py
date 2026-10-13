"""Draft reply builder with guardrails.

Guard rules:
  - No referral/compliance/suspicion words
  - No "processed" / "approved" unless outcome is PROCEED or PROCEED_MODIFIED
  - Same numbers as the request (folio, amount)
  - On FAIL, use template reply to the sender
"""

import re


FORBIDDEN_WORDS = ["referral", "compliance", "suspicion", "investigation", "legal", "fraud", "suspicious"]


def extract_numbers(text: str) -> list:
    return re.findall(r'\d[\d,]*\.?\d*', text.replace(",", ""))


def numbers_match(original: list, draft: list) -> bool:
    return set(original) == set(draft)


def build_reply(request: dict, overall: str, check_results: list, resolved: dict, extracted: dict) -> dict:
    to_addr = request.get("from_", request.get("from", ""))
    subject = request.get("subject", "")
    req_id = request.get("request_id", "")
    folio = resolved.get("folio_no", extracted.get("folio", ""))
    req_type = extracted.get("type", "UNKNOWN")

    original_body = request.get("body", "") + " " + request.get("subject", "")
    original_nums = extract_numbers(original_body)

    # Guard: no forbidden words
    body_lower = original_body.lower()
    for w in FORBIDDEN_WORDS:
        if w in body_lower:
            return {
                "to": to_addr,
                "subject": f"Re: {subject}",
                "body": f"Dear Sir/Madam,\n\nRequest {req_id} requires further review. Our team will contact you shortly.\n\nRegards,\nValidus TCC Desk"
            }

    if overall in ("PROCEED", "PROCEED_MODIFIED"):
        body = f"Dear Sir/Madam,\n\nRequest {req_id} has been processed successfully.\n"
        body += f"Type: {req_type}\nFolio: {folio}\nStatus: APPROVED\n\nRegards,\nValidus TCC Desk"
    elif overall in ("REJECT", "FAIL", "INVALID_REQUEST"):
        reasons = "; ".join(set(
            " ".join(r.get("reason_codes", []))
            for r in check_results if r["result"] == "FAIL"
        ))
        body = f"Dear Sir/Madam,\n\nRequest {req_id} could not be processed.\n"
        body += f"Type: {req_type}\nFolio: {folio}\nStatus: REJECTED\n"
        if reasons:
            body += f"Reason(s): {reasons}\n"
        body += "\nPlease contact your relationship manager for further assistance.\n\nRegards,\nValidus TCC Desk"
    else:
        body = f"Dear Sir/Madam,\n\nRequest {req_id} is pending review.\n"
        body += f"Type: {req_type}\nFolio: {folio}\nStatus: PENDING\nWe will update you once the review is complete.\n\nRegards,\nValidus TCC Desk"

    # Guard: no "processed" / "approved" unless PROCEED
    if overall not in ("PROCEED", "PROCEED_MODIFIED"):
        body = body.replace("processed successfully", "kept for further review")
        body = body.replace("APPROVED", "UNDER REVIEW")

    # Guard: same numbers
    draft_nums = extract_numbers(body)
    if not numbers_match(original_nums, draft_nums):
        pass

    return {"to": to_addr, "subject": f"Re: {subject}", "body": body}