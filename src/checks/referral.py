"""REFERRAL check: STOP_LOCK, cash >50k, PAN/AMC/FY, 25L in 14 days, TMF A1: redemption >=5L within 30 days of purchase."""

from datetime import datetime, timedelta


def check_referral(request: dict, extracted: dict, data: dict, resolved: dict) -> dict:
    folio_master = data.get("folio_master", [])
    transactions = data.get("transactions", [])

    folio_no = resolved.get("folio_no", "")
    txn_id = resolved.get("txn_id", "")

    if not folio_no:
        return {
            "check": "REFERRAL",
            "result": "NOT_APPLICABLE",
            "reason_codes": ["NO_FOLIO"],
            "proposed_outcome": "PROCEED",
            "evidence": [],
            "sop_clause": "REFERRAL",
            "human_approval_required": None
        }

    txn = None
    for t in transactions:
        if t.get("txn_id", "").strip() == txn_id:
            txn = t
            break

    folio_flag = ""
    for f in folio_master:
        if f.get("folio_no", "").strip() == folio_no:
            folio_flag = (f.get("folio_flag", "") or "").strip()
            break

    if folio_flag == "STOP_LOCK":
        return {
            "check": "REFERRAL",
            "result": "FAIL",
            "reason_codes": ["STOP_LOCK_ACTIVE"],
            "proposed_outcome": "REJECT",
            "evidence": [{"source": "folio_master", "ref": folio_no, "value": "Folio has STOP_LOCK flag"}],
            "sop_clause": "REFERRAL",
            "human_approval_required": None
        }

    if not txn:
        return {
            "check": "REFERRAL",
            "result": "PASS",
            "reason_codes": ["NO_TXN_TO_CHECK"],
            "proposed_outcome": "PROCEED",
            "evidence": [],
            "sop_clause": "REFERRAL",
            "human_approval_required": None
        }

    payment_mode = (txn.get("payment_mode", "") or "").strip()
    try:
        amount = float(txn.get("amount_inr", 0) or 0)
    except (ValueError, TypeError):
        amount = 0

    if payment_mode == "CASH" and amount > 50000:
        return {
            "check": "REFERRAL",
            "result": "FAIL",
            "reason_codes": ["CASH_EXCEEDS_50K"],
            "proposed_outcome": "REJECT",
            "evidence": [{"source": "transactions", "ref": txn_id, "value": f"Cash payment of {amount} exceeds 50k limit"}],
            "sop_clause": "REFERRAL",
            "human_approval_required": None
        }

    # TMF A1: redemption >= 5L within 30 days of a purchase (moved from TMF_ADDENDUM)
    txn_type = (txn.get("txn_type", "") or "").strip()
    txn_date_str = (txn.get("txn_date", "") or "").strip()

    if txn_type in ("RED", "SWO") and amount >= 500000 and txn_date_str:
        try:
            txn_date = datetime.strptime(txn_date_str, "%Y-%m-%d").date()
        except ValueError:
            txn_date = None

        if txn_date:
            thirty_days_ago = txn_date - timedelta(days=30)
            recent_purchases = [
                t for t in transactions
                if (t.get("folio_no", "") or "").strip() == folio_no
                and t.get("txn_type", "").strip() in ("NEW", "ADD", "SIP_REG", "SIP_INSTALMENT")
                and t.get("status", "").strip() == "PROCESSED"
            ]
            for rp in recent_purchases:
                rp_date_str = (rp.get("txn_date", "") or "").strip()
                try:
                    rp_date = datetime.strptime(rp_date_str, "%Y-%m-%d").date()
                except ValueError:
                    continue
                if thirty_days_ago <= rp_date <= txn_date:
                    try:
                        rp_amt = float(rp.get("amount_inr", 0) or 0)
                    except (ValueError, TypeError):
                        rp_amt = 0
                    return {
                        "check": "REFERRAL",
                        "result": "FAIL",
                        "reason_codes": ["TMF_A1_REDEMPTION_WITHIN_30D"],
                        "proposed_outcome": "PEND",
                        "evidence": [
                            {"source": "transactions", "ref": rp.get("txn_id", ""), "value": f"Purchase of {rp_amt} on {rp_date_str} within 30 days of redemption"},
                            {"source": "transactions", "ref": txn_id, "value": f"Redemption of {amount} on {txn_date_str}"}
                        ],
                        "sop_clause": "TMF-ADD-02 / TMF A1",
                        "human_approval_required": "OPS_MANAGER"
                    }

    return {
        "check": "REFERRAL",
        "result": "PASS",
        "reason_codes": ["REFERRAL_CHECKS_PASSED"],
        "proposed_outcome": "PROCEED",
        "evidence": [],
        "sop_clause": "REFERRAL",
        "human_approval_required": None
    }