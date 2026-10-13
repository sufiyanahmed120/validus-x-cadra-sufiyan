"""Validus TCC Desk FastAPI Service.

POST /requests - process mutual fund email requests with attachments
GET  /health  - health check

Response contract:
  checks always contains all 8 check_ids (NOT_APPLICABLE if unused).
  Extra fields documented in README.
"""

import os
import json
import csv
import re
import time
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI
from pydantic import BaseModel, Field
import uvicorn

from src.ingest import ingest_attachments
from src.extract import extract
from src.checks import run_all_checks
from src.decide import decide
from src.agent import validate_required_checks, safe_run
from src.reply import build_reply
from src.contract import normalize_response, validate_response

app = FastAPI(title="Validus TCC Desk API", version="1.0.0")

DATA_DIR = Path("Data/data")
PREPARED_DIR = Path("prepared")


class Attachment(BaseModel):
    file_name: str
    content_type: str
    content_base64: str


class InboxRequest(BaseModel):
    request_id: str
    received_at: str
    channel: str
    from_: str = Field(default="", alias="from")
    to: str = ""
    cc: str = ""
    subject: str = ""
    body: str = ""
    attachments: list[Attachment] = []


class HealthResponse(BaseModel):
    status: str


def load_csv_data():
    data = {}
    for fname in ["folio_master.csv", "kra_kyc_snapshot.csv", "transactions.csv", "bank_mandates.csv", "distributor_master.csv"]:
        fpath = PREPARED_DIR / fname
        if not fpath.exists():
            fpath = DATA_DIR / fname
        rows = []
        try:
            with open(fpath, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rows.append(dict(row))
        except Exception:
            rows = []
        key = fname.replace(".csv", "")
        data[key] = rows
    return data


def classify_request_type(email_text: str, subject: str, extracted: dict, txn: dict = None) -> str:
    if txn:
        txn_type = (txn.get("txn_type", "") or "").strip()
        txn_type_map = {
            "SIP_REG": "SIP_REGISTRATION",
            "SIP": "SIP_INSTALMENT",
            "SIP_INSTALMENT": "SIP_INSTALMENT",
            "NEW": "NEW_FOLIO_PURCHASE",
            "ADD": "ADDITIONAL_PURCHASE",
            "SWO": "ADDITIONAL_PURCHASE",
            "RED": "REDEMPTION",
            "SWI": "ADDITIONAL_PURCHASE",
        }
        return txn_type_map.get(txn_type, "ADDITIONAL_PURCHASE")

    text = f"{subject} {email_text}".upper()
    if "CHANGE OF BANK" in text or "COB" in text:
        return "CHANGE_OF_BANK"
    if "SIP" in text and ("REGIST" in text or "NEW SIP" in text):
        return "SIP_REGISTRATION"
    if "SIP" in text and ("INSTAL" in text or "DEBIT" in text):
        return "SIP_INSTALMENT"
    if "REDEMPTION" in text or "REDEEM" in text:
        return "REDEMPTION"
    if "FOLIO" in text and ("NEW" in text or "FRESH" in text or "OPEN" in text):
        return "NEW_FOLIO_PURCHASE"
    return "ADDITIONAL_PURCHASE"


def build_trace(check_results: list, model_calls: list = None) -> dict:
    return {
        "model_calls": model_calls or [],
        "tools_called": [r["check"] for r in check_results],
        "documents": [{"document": "Validus_TCC_SOP_v4.1", "version": "4.1"}]
    }


@app.post("/requests", response_model=None)
async def process_requests(req: InboxRequest):
    data = load_csv_data()

    start_time = time.time()
    model_calls = []
    req_dict = req.model_dump(by_alias=True)

    ingested = ingest_attachments([a.model_dump() for a in req.attachments])

    email_text = f"Subject: {req.subject}\nBody: {req.body}"
    att_texts = [{"file_name": a.get("file_name", ""), "text": a.get("text", "")} for a in ingested] if ingested else []
    extracted = extract(email_text, att_texts)

    if "error" not in extracted:
        model_calls.append({
            "model": "gemini-2.0-flash",
            "input_tokens": len(email_text.split()) + sum(len(t.get("text", "").split()) for t in att_texts),
            "output_tokens": len(json.dumps(extracted).split())
        })

    folio_norm = re.sub(r"[ /\-]", "", extracted.get("folio", ""))
    txn = None
    transactions = data.get("transactions", [])
    for t in transactions:
        tf = re.sub(r"[ /\-]", "", t.get("folio_no", ""))
        if tf == folio_norm and t.get("status", "").strip() == "PENDING_TCC":
            txn = t
            break

    req_type = classify_request_type(req.body, req.subject, extracted, txn)
    extracted["type"] = req_type

    if txn:
        txn_type = (txn.get("txn_type", "") or "").strip()
        type_map = {
            "SIP_REG": "SIP_REGISTRATION", "SIP": "SIP_INSTALMENT",
            "SIP_INSTALMENT": "SIP_INSTALMENT", "NEW": "NEW_FOLIO_PURCHASE",
            "ADD": "ADDITIONAL_PURCHASE", "RED": "REDEMPTION",
            "SWO": "ADDITIONAL_PURCHASE", "SWI": "ADDITIONAL_PURCHASE",
        }
        if txn_type in type_map:
            extracted["type"] = type_map[txn_type]

    raw_results, overall, human_approval, resolved, evidence = safe_run(
        run_all_checks, req_dict, extracted, data
    )

    if isinstance(raw_results, dict) and "error" in raw_results:
        overall = "PEND"
        raw_results = []
        resolved = {"folio_no": "", "amc_code": "", "first_holder_pan_masked": "", "txn_id": ""}
        evidence = []

    # Prefer the resolved transaction type (redemption vs purchase vs SIP) when available.
    resolved_folio = re.sub(r"[ /\-]", "", resolved.get("folio_no", ""))
    if resolved_folio:
        for t in data.get("transactions", []):
            if re.sub(r"[ /\-]", "", t.get("folio_no", "")) == resolved_folio and t.get("status", "").strip() == "PENDING_TCC":
                txn_type = (t.get("txn_type", "") or "").strip()
                type_map = {
                    "SIP_REG": "SIP_REGISTRATION", "SIP": "SIP_INSTALMENT",
                    "SIP_INSTALMENT": "SIP_INSTALMENT", "NEW": "NEW_FOLIO_PURCHASE",
                    "ADD": "ADDITIONAL_PURCHASE", "RED": "REDEMPTION",
                    "SWO": "ADDITIONAL_PURCHASE", "SWI": "ADDITIONAL_PURCHASE",
                }
                if txn_type in type_map:
                    extracted["type"] = type_map[txn_type]
                break

    # Decision engine (SOP 9.2)
    decision_result = decide(raw_results, overall, extracted.get("type", ""))
    final_overall = decision_result["decision"]
    approver_role = decision_result["approver_role"]

    # Agent: validate required checks
    validation_error = validate_required_checks(raw_results, extracted.get("type", ""))
    if validation_error:
        overall = "PEND"
        approver_role = approver_role or "OPS_MANAGER"

    # Build reply with guardrails
    draft_reply = build_reply(req_dict, final_overall, raw_results, resolved, extracted)

    trace = build_trace(raw_results, model_calls)

    chase_results = []
    for r in raw_results:
        chase_results.append({
            "check": r["check"],
            "result": r["result"],
            "reason_codes": r["reason_codes"],
            "proposed_outcome": r.get("proposed_outcome", r["result"]),
            "evidence": r.get("evidence", []),
            "sop_clause": r.get("sop_clause", "")
        })

    response = {
        "request_id": req.request_id,
        "request_type": extracted.get("type", "UNKNOWN"),
        "resolved": resolved,
        "decision": final_overall,
        "checks": chase_results,
        "human_approval_required": approver_role is not None,
        "approver_role": approver_role,
        "draft_reply": draft_reply,
        "trace": trace
    }

    response = normalize_response(response)
    errors = validate_response(response)
    if errors:
        raise ValueError(f"Contract violation: {errors}")
    return response


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok")


def main():
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("src.solution:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()