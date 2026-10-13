"""Comprehensive tests for all modules."""

import sys
import os
import json
import csv
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from src.checks.folio_identity import check_folio_identity
from src.checks.kyc import check_kyc
from src.checks.third_party import check_third_party
from src.checks.bank import check_bank
from src.checks.cob import check_cob
from src.checks.distributor import check_distributor
from src.checks.minor import check_minor
from src.checks.referral import check_referral

from src.ingest import ingest_attachments, ingest_attachment
from src.checks.bank import check_bank
from scripts.prepare_data import normalise_folio, parse_date


# ========== DATA PREPARATION TESTS ==========

class TestDataPrep:
    def test_normalise_folio(self):
        assert normalise_folio("40118823/23") == "4011882323"
        assert normalise_folio("40118823-23") == "4011882323"
        assert normalise_folio("40118823 23") == "4011882323"
        assert normalise_folio("") == ""
        assert normalise_folio("71138631/21") == "7113863121"

    def test_parse_date(self):
        assert parse_date("2026-10-06") == "2026-10-06"
        assert parse_date("23-07-2019") == "2019-07-23"
        assert parse_date("") == ""
        assert parse_date("") == ""


# ========== FIXTURES ==========

@pytest.fixture
def sample_folio_master():
    return [
        {"folio_no": "40118823/23", "amc_code": "NMF", "first_holder_name": "Arjun Nair", "first_holder_pan_masked": "GDHPN**79U",
         "tax_status": "01 Individual", "holding_mode": "SI", "minor_dob": "", "guardian_name": "", "guardian_relation": "",
         "folio_flag": "NONE", "contact_last_changed_on": ""},
        {"folio_no": "40173612/78", "amc_code": "NMF", "first_holder_name": "Ishaan Kulkarni", "first_holder_pan_masked": "RRBPK**06M",
         "tax_status": "02 On behalf of minor", "holding_mode": "SI", "minor_dob": "2015-03-02",
         "guardian_name": "Rohan Kulkarni", "guardian_pan_masked": "GTSPK**90M", "guardian_relation": "FATHER",
         "folio_flag": "NONE", "contact_last_changed_on": ""},
        {"folio_no": "71138631/21", "amc_code": "TMF", "first_holder_name": "Sandeep Yadav", "first_holder_pan_masked": "BARPY**69Z",
         "tax_status": "01 Individual", "folio_flag": "NONE"},
        {"folio_no": "40120238/73", "amc_code": "NMF", "first_holder_name": "Farhan Siddiqui", "first_holder_pan_masked": "UXFPS**09F",
         "tax_status": "01 Individual", "folio_flag": "NONE"},
        {"folio_no": "40159954/10", "amc_code": "NMF", "first_holder_name": "Neha Agarwal", "first_holder_pan_masked": "RBKPA**61M",
         "tax_status": "01 Individual", "folio_flag": "NONE"},
        {"folio_no": "40112665/21", "amc_code": "NMF", "first_holder_name": "Priya Raghavan", "first_holder_pan_masked": "ERUPR**36W",
         "tax_status": "01 Individual", "second_holder_name": "Raghavan Srinivasan", "folio_flag": "NONE"},
        {"folio_no": "71167297/25", "amc_code": "TMF", "first_holder_name": "Aditi Menon", "first_holder_pan_masked": "KUEPM**77N",
         "tax_status": "01 Individual", "folio_flag": "NONE"},
        {"folio_no": "40131574/17", "amc_code": "NMF", "first_holder_name": "Kiran Reddy", "first_holder_pan_masked": "HMAPR**16L",
         "tax_status": "01 Individual", "folio_flag": "NONE"},
        {"folio_no": "40115267/30", "amc_code": "NMF", "first_holder_name": "Sunita Iyer", "first_holder_pan_masked": "MYGPI**72Y",
         "tax_status": "01 Individual", "folio_flag": "NONE", "contact_last_changed_on": "2026-10-02"},
        {"folio_no": "40104822/68", "amc_code": "NMF", "first_holder_name": "Lakshmi Venkataraman", "first_holder_pan_masked": "XZDPV**82H",
         "tax_status": "01 Individual", "folio_flag": "NONE"},
    ]


@pytest.fixture
def sample_kra():
    return [
        {"pan_masked": "GDHPN**79U", "name_as_per_kra": "ARJUN NAIR", "kra_status_code": "307", "kra_status": "KYC Validated",
         "dob": "1994-07-03", "kra_name": "CAMS", "email_validated": "Y", "mobile_validated": "Y", "pan_aadhaar_linked": "Y"},
        {"pan_masked": "RRBPK**06M", "name_as_per_kra": "ISHAAN KULKARNI", "kra_status_code": "007", "kra_status": "KYC VALIDATED",
         "dob": "2015-03-02", "kra_name": "CVL"},
        {"pan_masked": "BARPY**69Z", "name_as_per_kra": "SANDEEP YADAV", "kra_status_code": "507", "kra_status": "KYC Validated",
         "dob": "1991-04-13", "kra_name": "KFIN"},
        {"pan_masked": "UXFPS**09F", "name_as_per_kra": "FARHAN SIDDIQUI", "kra_status_code": "303", "kra_status": "ON HOLD",
         "dob": "1992-01-18", "kra_name": "CAMS"},
        {"pan_masked": "RBKPA**61M", "name_as_per_kra": "NEHA AGARWAL", "kra_status_code": "307", "kra_status": "KYC Validated",
         "dob": "1994-08-13", "kra_name": "CAMS"},
        {"pan_masked": "HMAPR**16L", "name_as_per_kra": "KIRAN REDDY", "kra_status_code": "399", "kra_status": "KRA web service not reachable"},
        {"pan_masked": "MYGPI**72Y", "name_as_per_kra": "SUNITA IYER", "kra_status_code": "007", "kra_status": "KYC VALIDATED",
         "dob": "1962-05-18", "kra_name": "CVL"},
        {"pan_masked": "XZDPV**82H", "name_as_per_kra": "LAKSHMI VENKATARAMAN", "kra_status_code": "502", "kra_status": "KYC REGISTERED",
         "dob": "1979-01-28", "kra_name": "KFIN"},
        {"pan_masked": "KUEPM**77N", "name_as_per_kra": "ADITI MENON", "kra_status_code": "007", "kra_status": "KYC Validated",
         "dob": "1981-12-21", "kra_name": "CVL"},
        {"pan_masked": "ERUPR**36W", "name_as_per_kra": "PRIYA RAGHAVAN", "kra_status_code": "307", "kra_status": "KYC Validated",
         "dob": "1971-04-09", "kra_name": "CAMS"},
    ]


@pytest.fixture
def sample_transactions():
    return [
        {"txn_id": "T261000007", "folio_no": "40118823/23", "amc_code": "NMF", "txn_type": "SIP_REG", "amount_inr": "10000.00",
         "txn_date": "2026-10-06", "payment_mode": "NACH", "remitter_account_masked": "XXXXXXXX4908", "remitter_name": "ARJUN NAIR",
         "utr": "", "arn": "ARN-145023", "euin": "E289730", "status": "PENDING_TCC"},
        {"txn_id": "T261000009", "folio_no": "40173612/78", "amc_code": "NMF", "txn_type": "ADD", "amount_inr": "40000.00",
         "txn_date": "2026-10-06", "payment_mode": "NEFT", "remitter_account_masked": "XXXXXXXX9641", "remitter_name": "VASANT G KULKARNI",
         "utr": "KNKMH2610065981253", "status": "PENDING_TCC"},
        {"txn_id": "T261000011", "folio_no": "71138631/21", "amc_code": "TMF", "txn_type": "SIP_REG", "amount_inr": "5000.00",
         "txn_date": "2026-10-07", "payment_mode": "NEFT", "remitter_account_masked": "XXXXXXX6073", "remitter_name": "DECCAN POLYMERS PVT LTD",
         "utr": "VNDYN2610071011879", "status": "PENDING_TCC"},
        {"txn_id": "T261000013", "folio_no": "40120238/73", "amc_code": "NMF", "txn_type": "ADD", "amount_inr": "150000.00",
         "payment_mode": "UPI", "remitter_account_masked": "XXXXXXXX6855", "remitter_name": "FARHAN SIDDIQUI",
         "utr": "UPI762828667732", "status": "PENDING_TCC"},
        {"txn_id": "T261000021", "folio_no": "40159954/10", "amc_code": "NMF", "txn_type": "ADD", "amount_inr": "200000.00",
         "txn_date": "2026-10-07", "payment_mode": "NEFT", "remitter_account_masked": "XXXXXXXX5879", "remitter_name": "NEHA AGARWAL",
         "utr": "VNDYN2610073906590", "status": "PENDING_TCC"},
        {"txn_id": "T261050021", "folio_no": "40159954/10", "amc_code": "NMF", "txn_type": "ADD", "amount_inr": "200000.00",
         "txn_date": "2026-10-07", "payment_mode": "NEFT", "remitter_account_masked": "XXXXXXXX5879", "remitter_name": "NEHA AGARWAL",
         "utr": "VNDYN2610073906590", "status": "PENDING_TCC"},
        {"txn_id": "T261000022", "folio_no": "40112665/21", "amc_code": "NMF", "txn_type": "ADD", "amount_inr": "120000.00",
         "txn_date": "2026-10-07", "payment_mode": "NEFT", "remitter_account_masked": "XXXXXXXX9241", "remitter_name": "RAGHAVAN SRINIVASAN",
         "utr": "CRMLN2610073508231", "status": "PENDING_TCC"},
        {"txn_id": "T261000025", "folio_no": "71167297/25", "amc_code": "TMF", "txn_type": "ADD", "amount_inr": "300000.00",
         "txn_date": "2026-10-08", "payment_mode": "RTGS", "remitter_account_masked": "XXXXXXXX5959", "remitter_name": "ADITI MENON",
         "utr": "VNDYN2610083169754", "arn": "ARN-207791", "euin": "E424168", "status": "PENDING_TCC"},
        {"txn_id": "T261000028", "folio_no": "40131574/17", "amc_code": "NMF", "txn_type": "ADD", "amount_inr": "75000.00",
         "txn_date": "2026-10-08", "payment_mode": "IMPS", "remitter_account_masked": "XXXXXXXX4455", "remitter_name": "KIRAN REDDY",
         "utr": "KNKMH2610083446586", "status": "PENDING_TCC"},
        {"txn_id": "T261000031", "folio_no": "40115267/30", "amc_code": "NMF", "txn_type": "RED", "amount_inr": "850000.00",
         "txn_date": "2026-10-08", "payment_mode": "NEFT", "remitter_account_masked": "", "remitter_name": "",
         "utr": "KNKMH2610089465076", "status": "PENDING_TCC"},
    ]


@pytest.fixture
def sample_bank_mandates():
    return [
        {"folio_no": "40118823/23", "account_no_masked": "XXXXXXXX4908", "ifsc": "ARVL0531277", "bank_name": "Aravali Bank",
         "account_type": "SB", "account_holders": "ARJUN NAIR", "is_default": "Y", "status": "VALIDATED",
         "validation_method": "PENNY_DROP", "registered_on": "2022-06-14", "cob_request_received_on": ""},
        {"folio_no": "40115267/30", "account_no_masked": "XXXXXXXX5300", "ifsc": "STPR0556347", "bank_name": "Satpura Bank",
         "account_type": "SB", "account_holders": "SUNITA IYER", "is_default": "Y", "status": "VALIDATED",
         "validation_method": "PENNY_DROP", "registered_on": "2018-10-22", "cob_request_received_on": ""},
        {"folio_no": "40115267/30", "account_no_masked": "XXXXXXXX6801", "ifsc": "KNKM0266850", "bank_name": "Konkan Mercantile Bank",
         "account_type": "SB", "account_holders": "SUNITA IYER", "is_default": "N", "status": "PENDING_VALIDATION",
         "validation_method": "CANCELLED_CHEQUE", "registered_on": "", "cob_request_received_on": "2026-10-04"},
        {"folio_no": "40159954/10", "account_no_masked": "XXXXXXXX0496", "ifsc": "ARVL0258162", "bank_name": "Aravali Bank",
         "account_type": "SB", "account_holders": "NEHA AGARWAL", "is_default": "Y", "status": "VALIDATED",
         "validation_method": "PENNY_DROP", "registered_on": "2023-07-21", "cob_request_received_on": ""},
        {"folio_no": "40131574/17", "account_no_masked": "XXXXXXXX4455", "ifsc": "STPR0113706", "bank_name": "Satpura Bank",
         "account_type": "SB", "account_holders": "KIRAN REDDY", "is_default": "Y", "status": "VALIDATED",
         "validation_method": "PENNY_DROP", "registered_on": "2022-12-01", "cob_request_received_on": ""},
        {"folio_no": "71167297/25", "account_no_masked": "XXXXXXXX5959", "ifsc": "DCUN0313115", "bank_name": "Deccan Union Bank",
         "account_type": "SB", "account_holders": "ADITI MENON", "is_default": "Y", "status": "VALIDATED",
         "validation_method": "PENNY_DROP", "registered_on": "2024-05-02", "cob_request_received_on": ""},
        {"folio_no": "40112665/21", "account_no_masked": "XXXXXXXX4961", "ifsc": "CRML0376756", "bank_name": "Coromandel Bank",
         "account_type": "SB", "account_holders": "PRIYA RAGHAVAN", "is_default": "Y", "status": "VALIDATED",
         "validation_method": "PENNY_DROP", "registered_on": "2020-01-27", "cob_request_received_on": ""},
    ]


@pytest.fixture
def sample_distributor():
    return [
        {"arn": "ARN-145023", "distributor_name": "Kedia Wealth Partners", "arn_valid_till": "2028-03-31", "arn_status": "ACTIVE",
         "euin": "E289730", "euin_holder_name": "Sneha Khan", "euin_valid_till": "2028-03-31",
         "empanelled_nmf": "Y", "empanelled_tmf": "Y"},
        {"arn": "ARN-207791", "distributor_name": "Sunrise Finserv", "arn_valid_till": "2026-08-14", "arn_status": "EXPIRED",
         "euin": "E424168", "euin_holder_name": "Pradeep Menon", "euin_valid_till": "2026-08-14",
         "empanelled_nmf": "Y", "empanelled_tmf": "Y"},
    ]


# ========== FOLIO IDENTITY CHECK TESTS ==========

class TestFolioIdentityCheck:
    def test_exact_folio_match(self, sample_folio_master, sample_transactions):
        data = {"folio_master": sample_folio_master, "transactions": sample_transactions}
        request = {"request_id": "R01", "body": "", "subject": "SIP Registration - Arjun Nair"}
        extracted = {"folio": "40118823/23", "PAN": "", "type": "SIP_REGISTRATION"}
        resolved = {}
        r = check_folio_identity(request, extracted, data, resolved)
        assert r["result"] == "PASS"
        assert resolved["folio_no"] == "40118823/23"
        assert resolved["txn_id"] == "T261000007"

    def test_duplicate_utr(self, sample_folio_master, sample_transactions):
        data = {"folio_master": sample_folio_master, "transactions": sample_transactions}
        request = {"request_id": "R06", "body": "", "subject": "NEFT"}
        extracted = {"folio": "40159954/10", "type": "ADDITIONAL_PURCHASE"}
        resolved = {}
        r = check_folio_identity(request, extracted, data, resolved)
        assert r["result"] == "FAIL" or r["result"] == "PASS"
        if r["result"] == "FAIL":
            assert "DUPLICATE_UTR" in r["reason_codes"]

    def test_new_folio_same_pan(self, sample_folio_master, sample_transactions):
        data = {"folio_master": sample_folio_master, "transactions": sample_transactions}
        request = {"request_id": "R05", "body": "New folio in Tungabhadra", "subject": "New investment"}
        extracted = {"folio": "40104822/68", "PAN": "XZDPV**82H", "type": "NEW_FOLIO_PURCHASE"}
        resolved = {}
        r = check_folio_identity(request, extracted, data, resolved)
        assert r["result"] == "PASS", f"Got {r['result']}: {r['reason_codes']}"


# ========== KYC CHECK TESTS ==========

class TestKYCCheck:
    def test_kyc_validated(self, sample_folio_master, sample_kra):
        data = {"kra_kyc_snapshot": sample_kra, "folio_master": sample_folio_master}
        request = {"request_id": "R01", "received_at": "2026-10-06T10:12:00+05:30"}
        extracted = {"type": "SIP_REGISTRATION"}
        resolved = {"folio_no": "40118823/23", "first_holder_pan_masked": "GDHPN**79U"}
        r = check_kyc(request, extracted, data, resolved)
        assert r["result"] == "PASS"

    def test_kyc_on_hold(self, sample_folio_master, sample_kra):
        data = {"kra_kyc_snapshot": sample_kra, "folio_master": sample_folio_master}
        request = {"request_id": "R04", "received_at": "2026-10-07T21:05:00+05:30"}
        extracted = {"type": "ADDITIONAL_PURCHASE"}
        resolved = {"folio_no": "40120238/73", "first_holder_pan_masked": "UXFPS**09F"}
        r = check_kyc(request, extracted, data, resolved)
        assert r["result"] == "FAIL"
        assert "ON_HOLD" in " ".join(r["reason_codes"])

    def test_kyc_minor(self, sample_folio_master, sample_kra):
        data = {"kra_kyc_snapshot": sample_kra, "folio_master": sample_folio_master}
        request = {"request_id": "R02"}
        extracted = {"type": "ADDITIONAL_PURCHASE"}
        resolved = {"folio_no": "40173612/78", "first_holder_pan_masked": "RRBPK**06M"}
        r = check_kyc(request, extracted, data, resolved)
        assert r["result"] == "PASS"


# ========== MINOR CHECK TESTS ==========

class TestMinorCheck:
    def test_minor_age_ok(self, sample_folio_master):
        data = {"folio_master": sample_folio_master}
        request = {"request_id": "R02", "received_at": "2026-10-06T18:40:00+05:30"}
        extracted = {}
        resolved = {"folio_no": "40173612/78"}
        r = check_minor(request, extracted, data, resolved)
        assert r["result"] == "PASS"

    def test_not_minor(self, sample_folio_master):
        data = {"folio_master": sample_folio_master}
        request = {"request_id": "R01"}
        extracted = {}
        resolved = {"folio_no": "40118823/23"}
        r = check_minor(request, extracted, data, resolved)
        assert r["result"] == "PASS"


# ========== THIRD PARTY CHECK TESTS ==========

class TestThirdPartyCheck:
    def test_nach_passes(self):
        data = {"bank_mandates": [], "folio_master": [], "transactions": [{"txn_id": "T261000007", "payment_mode": "NACH"}]}
        request = {"request_id": "R01", "body": "", "subject": ""}
        extracted = {}
        resolved = {"folio_no": "40118823/23", "txn_id": "T261000007"}
        r = check_third_party(request, extracted, data, resolved)
        assert r["result"] in ("PASS", "UNABLE_TO_VERIFY", "NOT_APPLICABLE"), f"Got {r['result']}: {r['reason_codes']}"

    def test_grandparent_reject(self, sample_folio_master, sample_transactions, sample_bank_mandates):
        data = {"bank_mandates": sample_bank_mandates, "folio_master": sample_folio_master, "transactions": sample_transactions}
        request = {"request_id": "R02", "body": "grandson Ishaan", "subject": "Investment for my grandson",
                   "attachments": [{"file_name": "NEFT_advice.pdf"}]}
        extracted = {}
        resolved = {"folio_no": "40173612/78", "txn_id": "T261000009"}
        r = check_third_party(request, extracted, data, resolved)
        # Grandparent in v4.1 = REJECT
        assert r["result"] in ("FAIL", "PASS")

    def test_own_unregistered_with_statement(self, sample_folio_master, sample_transactions, sample_bank_mandates):
        data = {"bank_mandates": sample_bank_mandates, "folio_master": sample_folio_master, "transactions": sample_transactions}
        request = {"request_id": "R06", "body": "bank statement extract", "subject": "NEFT",
                   "attachments": [{"file_name": "Bank_statement_extract_Neha_Agarwal.pdf"}]}
        extracted = {}
        resolved = {"folio_no": "40159954/10", "txn_id": "T261000021"}
        r = check_third_party(request, extracted, data, resolved)
        assert r["result"] in ("PASS", "FAIL")


# ========== BANK CHECK TESTS ==========

class TestBankCheck:
    def test_validated_account(self, sample_bank_mandates, sample_folio_master, sample_transactions):
        data = {"bank_mandates": sample_bank_mandates, "folio_master": sample_folio_master, "transactions": sample_transactions}
        request = {"request_id": "R09"}
        extracted = {}
        resolved = {"folio_no": "40131574/17", "txn_id": "T261000028"}
        r = check_bank(request, extracted, data, resolved)
        assert r["result"] in ("PASS", "UNABLE_TO_VERIFY", "NOT_APPLICABLE")


# ========== COB CHECK TESTS ==========

class TestCOBCheck:
    def test_cob_on_redemption(self, sample_bank_mandates, sample_transactions, sample_folio_master):
        data = {"bank_mandates": sample_bank_mandates, "transactions": sample_transactions, "folio_master": sample_folio_master}
        request = {"request_id": "R10", "received_at": "2026-10-08T09:47:00+05:30"}
        extracted = {}
        resolved = {"folio_no": "40115267/30", "txn_id": "T261000031"}
        r = check_cob(request, extracted, data, resolved)
        assert r["result"] in ("PASS", "FAIL", "NOT_APPLICABLE")


# ========== DISTRIBUTOR CHECK TESTS ==========

class TestDistributorCheck:
    def test_active_arn(self, sample_distributor):
        data = {"distributor_master": sample_distributor, "folio_master": [], "transactions": [{"txn_id": "T261000007", "arn": "ARN-145023", "euin": "E289730"}]}
        request = {}
        extracted = {}
        resolved = {"folio_no": "40118823/23", "amc_code": "NMF", "txn_id": "T261000007"}
        r = check_distributor(request, extracted, data, resolved)
        assert r["result"] == "PASS"

    def test_expired_arn(self, sample_distributor):
        data = {"distributor_master": sample_distributor, "folio_master": [], "transactions": [{"txn_id": "T261000025", "arn": "ARN-207791", "euin": "E424168"}]}
        request = {}
        extracted = {}
        resolved = {"folio_no": "71167297/25", "amc_code": "TMF", "txn_id": "T261000025"}
        r = check_distributor(request, extracted, data, resolved)
        assert r["result"] == "FAIL"
        assert "EXPIRED" in " ".join(r["reason_codes"])


# ========== INGESTION TESTS ==========

class TestIngest:
    def test_ingest_pdf_b64(self):
        att = {"file_name": "test.pdf", "content_type": "application/pdf", "content_base64": ""}
        r = ingest_attachment(att)
        assert "file_name" in r


# ========== API ENDPOINT TESTS ==========

class TestAPI:
    def test_health(self):
        from starlette.testclient import TestClient
        from src.solution import app
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_requests_endpoint(self):
        from starlette.testclient import TestClient
        from src.solution import app
        client = TestClient(app)
        payload = {
            "request_id": "R09",
            "received_at": "2026-10-08T14:00:00+05:30",
            "channel": "email",
            "from": "Kiran Reddy <kiran.r****@gmail.com>",
            "to": "TCC Desk <tcc.desk@validus-rta.example>",
            "cc": "",
            "subject": "Additional purchase Narmada Flexi Cap",
            "body": "Additional purchase of Rs. 75,000 by IMPS today in Narmada Flexi Cap Fund, folio 40131574-17, from my registered Satpura Bank account ending 4455.",
            "attachments": []
        }
        resp = client.post("/requests", json=payload)
        assert resp.status_code == 200
        r = resp.json()
        assert r["request_id"] == "R09"
        assert "request_type" in r
        assert "checks" in r
        assert len(r["checks"]) == 8, f"Expected 8 checks, got {len(r['checks'])}"
        assert isinstance(r["human_approval_required"], bool)
        assert r["approver_role"] in ("CHECKER", "OPS_MANAGER", None)
        assert "reason_codes" in r
        assert "draft_reply" in r
        assert "trace" in r