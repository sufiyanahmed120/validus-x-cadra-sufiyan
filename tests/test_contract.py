"""Contract conformance: POST every inbox request and validate the response shape."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from starlette.testclient import TestClient

from src.solution import app
from src.contract import validate_response, OUTCOMES, SOP_REASON_CODES

client = TestClient(app)

REQUESTS_FILE = Path(__file__).parent.parent / "Data" / "inbox" / "requests.json"
EXPECTED_CHECK_IDS = {
    "FOLIO_IDENTITY", "KYC_STATUS", "THIRD_PARTY_PAYMENT", "BANK_MANDATE",
    "COB_COOLING", "DISTRIBUTOR_CODE", "MINOR_RULES", "REFERRAL",
}


def load_requests():
    with open(REQUESTS_FILE, encoding="utf-8") as f:
        return json.load(f)


def test_every_request_conforms_to_contract():
    for req in load_requests():
        resp = client.post("/requests", json=req)
        assert resp.status_code == 200, f"{req['request_id']}: HTTP {resp.status_code}"
        body = resp.json()

        assert validate_response(body) == [], f"{req['request_id']}: {validate_response(body)}"

        assert body["request_id"] == req["request_id"]
        assert body["outcomes"] in OUTCOMES
        assert "decision" not in body
        assert isinstance(body["human_approval_required"], bool)
        assert body["approver_role"] in ("CHECKER", "OPS_MANAGER", None)
        assert set(body["reason_codes"]).issubset(SOP_REASON_CODES)

        check_ids = {c["check_id"] for c in body["checks"]}
        assert check_ids == EXPECTED_CHECK_IDS, f"{req['request_id']}: {check_ids ^ EXPECTED_CHECK_IDS}"

        for c in body["checks"]:
            assert "check" not in c
            assert c["proposed_outcome"] in OUTCOMES
            assert set(c["reason_codes"]).issubset(SOP_REASON_CODES)

        folio = body["resolved"]["folio_no"]
        if folio:
            assert len(folio) == 11 and folio[8] == "/", f"{req['request_id']}: folio {folio}"


def test_r10_redemption_contract():
    req = next(r for r in load_requests() if r["request_id"] == "R10")
    body = client.post("/requests", json=req).json()
    assert body["outcomes"] == "HOLD_AND_REFER"
    assert body["approver_role"] == "OPS_MANAGER"
    assert body["human_approval_required"] is True

    tpp = next(c for c in body["checks"] if c["check_id"] == "THIRD_PARTY_PAYMENT")
    assert tpp["result"] == "NOT_APPLICABLE"

    assert "COB_COOLING" in body["reason_codes"]
    assert "BANK_PROOF_REQUIRED" in body["reason_codes"]

