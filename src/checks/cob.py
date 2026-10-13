"""COB_COOLING check (SOP 6.4, 6.5): change of bank cooling period.

6.4: COB received 0-10 calendar days before a redemption = FAIL, outcome PEND_COB.
6.5: Contact changed 0-30 days before that COB = FAIL, outcome HOLD_AND_REFER.
"""

from datetime import datetime, timezone, timedelta


def _parse_iso_dt(s: str) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def _normalise_dt(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


def check_cob(request: dict, extracted: dict, data: dict, resolved: dict) -> dict:
    bank_mandates = data.get("bank_mandates", [])
    transactions = data.get("transactions", [])
    folio_master = data.get("folio_master", [])

    folio_no = resolved.get("folio_no", "")
    txn_id = resolved.get("txn_id", "")

    if not folio_no or not txn_id:
        return {
            "check": "COB_COOLING",
            "result": "NOT_APPLICABLE",
            "reason_codes": ["NO_FOLIO_OR_TXN"],
            "proposed_outcome": "PROCEED",
            "evidence": [],
            "sop_clause": "6.4",
            "human_approval_required": None
        }

    txn = None
    for t in transactions:
        if t.get("txn_id", "").strip() == txn_id:
            txn = t
            break

    if not txn:
        return {
            "check": "COB_COOLING",
            "result": "UNABLE_TO_VERIFY",
            "reason_codes": ["TXN_NOT_FOUND"],
            "proposed_outcome": "PEND",
            "evidence": [],
            "sop_clause": "6.4",
            "human_approval_required": "OPS_MANAGER"
        }

    txn_type = (txn.get("txn_type", "") or "").strip()

    if txn_type not in ("RED",):
        return {
            "check": "COB_COOLING",
            "result": "PASS",
            "reason_codes": ["NOT_REDEMPTION"],
            "proposed_outcome": "PROCEED",
            "evidence": [],
            "sop_clause": "6.4",
            "human_approval_required": None
        }

    cob_accounts = [b for b in bank_mandates if b.get("folio_no", "").strip() == folio_no
                    and (b.get("cob_request_received_on", "") or "").strip()]

    if not cob_accounts:
        return {
            "check": "COB_COOLING",
            "result": "PASS",
            "reason_codes": ["NO_COB_REQUEST"],
            "proposed_outcome": "PROCEED",
            "evidence": [],
            "sop_clause": "6.4",
            "human_approval_required": None
        }

    received_dt = _parse_iso_dt(request.get("received_at", ""))
    if received_dt is None:
        return {
            "check": "COB_COOLING",
            "result": "UNABLE_TO_VERIFY",
            "reason_codes": ["INVALID_DATE"],
            "proposed_outcome": "PEND",
            "evidence": [],
            "sop_clause": "6.4",
            "human_approval_required": "OPS_MANAGER"
        }
    received_dt = _normalise_dt(received_dt)

    for cob in cob_accounts:
        cob_date_str = (cob.get("cob_request_received_on", "") or "").strip()
        if not cob_date_str:
            continue
        try:
            cob_date = datetime.strptime(cob_date_str, "%Y-%m-%d")
        except ValueError:
            continue

        days_between = (received_dt - cob_date).days

        if 0 <= days_between <= 10:
            # SOP 6.5: check contact changed 0-30 days before the COB
            contact_last_changed = ""
            for f in folio_master:
                if f.get("folio_no", "").strip() == folio_no:
                    contact_last_changed = (f.get("contact_last_changed_on", "") or "").strip()
                    break
            if contact_last_changed:
                try:
                    contact_dt = datetime.strptime(contact_last_changed, "%Y-%m-%d")
                    contact_days_before_cob = (cob_date - contact_dt).days
                    if 0 <= contact_days_before_cob <= 30:
                        return {
                            "check": "COB_COOLING",
                            "result": "FAIL",
                            "reason_codes": ["COB_COOLING", "HIGH_RISK_CONTACT_COB"],
                            "proposed_outcome": "HOLD_AND_REFER",
                            "evidence": [
                                {"source": "bank_mandates", "ref": folio_no, "value": f"COB received {cob_date_str}, {days_between} days before redemption (within 0-10)"},
                                {"source": "folio_master", "ref": folio_no, "value": f"Contact last changed {contact_last_changed}, {contact_days_before_cob} days before COB"}
                            ],
                            "sop_clause": "6.4, 6.5",
                            "human_approval_required": None
                        }
                except ValueError:
                    pass

            return {
                "check": "COB_COOLING",
                "result": "FAIL",
                "reason_codes": ["COB_COOLING"],
                "proposed_outcome": "PEND",
                "evidence": [{"source": "bank_mandates", "ref": folio_no, "value": f"COB received {cob_date_str}, {days_between} days before redemption (within 0-10)"}],
                "sop_clause": "6.4",
                "human_approval_required": None
            }

    return {
        "check": "COB_COOLING",
        "result": "PASS",
        "reason_codes": ["COB_OUTSIDE_COOLING"],
        "proposed_outcome": "PROCEED",
        "evidence": [{"source": "bank_mandates", "ref": folio_no, "value": "COB outside 0-10 day window"}],
        "sop_clause": "6.4",
        "human_approval_required": None
    }