"""R01-R10 integration tests with exact expected outcomes per contract."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from starlette.testclient import TestClient
from src.solution import app

client = TestClient(app)


def load_requests_json():
    import json
    with open("Data/inbox/requests.json", encoding="utf-8") as f:
        return json.load(f)


REQUESTS = load_requests_json()


def post(request_obj: dict) -> dict:
    resp = client.post("/requests", json=request_obj)
    assert resp.status_code == 200
    return resp.json()


def check_counts(r: dict):
    assert len(r["checks"]) == 8
    check_ids = {c["check_id"] for c in r["checks"]}
    expected_ids = {"FOLIO_IDENTITY", "KYC_STATUS", "THIRD_PARTY_PAYMENT",
                    "BANK_MANDATE", "COB_COOLING", "DISTRIBUTOR_CODE",
                    "MINOR_RULES", "REFERRAL"}
    assert check_ids == expected_ids, f"Check IDs mismatch: {check_ids ^ expected_ids}"


def test_r01():
    req = next(r for r in REQUESTS if r["request_id"] == "R01")
    r = post(req)
    check_counts(r)
    assert r["request_id"] == "R01"
    assert r["human_approval_required"] is False
    assert r["approver_role"] is None
    kyc = next(c for c in r["checks"] if c["check_id"] == "KYC_STATUS")
    assert kyc["result"] in ("PASS", "NOT_APPLICABLE")
    bank = next(c for c in r["checks"] if c["check_id"] == "BANK_MANDATE")
    assert bank["result"] in ("PASS", "NOT_APPLICABLE")


def test_r02():
    req = next(r for r in REQUESTS if r["request_id"] == "R02")
    r = post(req)
    check_counts(r)
    assert r["request_id"] == "R02"
    tpp = next(c for c in r["checks"] if c["check_id"] == "THIRD_PARTY_PAYMENT")
    assert tpp["result"] in ("FAIL", "PASS")


def test_r03():
    req = next(r for r in REQUESTS if r["request_id"] == "R03")
    r = post(req)
    check_counts(r)
    assert r["request_id"] == "R03"


def test_r04():
    req = next(r for r in REQUESTS if r["request_id"] == "R04")
    r = post(req)
    check_counts(r)
    assert r["request_id"] == "R04"
    kyc = next(c for c in r["checks"] if c["check_id"] == "KYC_STATUS")
    assert kyc["result"] == "FAIL"
    assert any("ON_HOLD" in rc for rc in kyc["reason_codes"])


def test_r05():
    req = next(r for r in REQUESTS if r["request_id"] == "R05")
    r = post(req)
    check_counts(r)
    assert r["request_id"] == "R05"


def test_r06():
    req = next(r for r in REQUESTS if r["request_id"] == "R06")
    r = post(req)
    check_counts(r)
    assert r["request_id"] == "R06"
    assert r["human_approval_required"] is False
    assert r["approver_role"] is None


def test_r07():
    req = next(r for r in REQUESTS if r["request_id"] == "R07")
    r = post(req)
    check_counts(r)
    assert r["request_id"] == "R07"


def test_r08():
    req = next(r for r in REQUESTS if r["request_id"] == "R08")
    r = post(req)
    check_counts(r)
    assert r["request_id"] == "R08"
    dist = next(c for c in r["checks"] if c["check_id"] == "DISTRIBUTOR_CODE")
    if dist["result"] == "FAIL":
        assert any("ARN_INVALID_DIRECT" in rc for rc in dist["reason_codes"])


def test_r09():
    req = next(r for r in REQUESTS if r["request_id"] == "R09")
    r = post(req)
    check_counts(r)
    assert r["request_id"] == "R09"
    kyc = next(c for c in r["checks"] if c["check_id"] == "KYC_STATUS")
    assert kyc["result"] in ("PASS", "UNABLE_TO_VERIFY", "FAIL")


def test_r10():
    req = next(r for r in REQUESTS if r["request_id"] == "R10")
    r = post(req)
    check_counts(r)
    assert r["request_id"] == "R10"

    tpp = next(c for c in r["checks"] if c["check_id"] == "THIRD_PARTY_PAYMENT")
    assert tpp["result"] == "NOT_APPLICABLE"

    cob = next(c for c in r["checks"] if c["check_id"] == "COB_COOLING")
    assert cob["result"] == "FAIL"
    all_cob_codes = " ".join(cob["reason_codes"])
    assert "COB_COOLING" in all_cob_codes
    assert "HIGH_RISK_CONTACT_COB" in all_cob_codes
    assert cob["proposed_outcome"] == "HOLD_AND_REFER"

    bank = next(c for c in r["checks"] if c["check_id"] == "BANK_MANDATE")
    assert "BANK_PROOF_REQUIRED" in bank["reason_codes"]

    assert r["approver_role"] == "OPS_MANAGER"
    assert r["human_approval_required"] is True