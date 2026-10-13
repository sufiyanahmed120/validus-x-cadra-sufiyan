"""Eval runner: score outcomes+codes; count UNSAFE (let through wrongly) and over-cautious errors; save to eval/results/<timestamp>/."""

import json
import sys
import os
from pathlib import Path
from datetime import datetime
from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.solution import app

client = TestClient(app)

EVAL_DIR = Path(__file__).parent
EXPECTED_FILE = EVAL_DIR / "expected.json"
RESULTS_DIR = EVAL_DIR / "results"

PENDING_DECISIONS = {"PEND", "HOLD_AND_REFER", "INVALID_REQUEST"}
SAFE_DECISIONS = {"PROCEED", "PROCEED_MODIFIED"}
REJECT_DECISIONS = {"FAIL", "REJECT"}


def load_expected():
    with open(EXPECTED_FILE) as f:
        return json.load(f)


def load_requests():
    inbox_file = Path(__file__).parent.parent / "Data" / "inbox" / "requests.json"
    with open(inbox_file) as f:
        return json.load(f)


def post_request(req_obj: dict) -> dict:
    resp = client.post("/requests", json=req_obj)
    assert resp.status_code == 200
    return resp.json()


def evaluate():
    expected_list = load_expected()
    requests_list = load_requests()

    expected_map = {e["request_id"]: e for e in expected_list}
    req_map = {r["request_id"]: r for r in requests_list}

    results = []
    unsafe_count = 0
    overcautious_count = 0
    total = len(expected_list)
    correct_decision = 0

    for exp in expected_list:
        rid = exp["request_id"]
        req = req_map.get(rid)
        if not req:
            results.append({"request_id": rid, "error": "request not found in inbox"})
            continue

        actual = post_request(req)
        actual_decision = actual.get("outcome", "UNKNOWN")
        expected_decision = exp["expected_decision"]

        actual_codes = set()
        for c in actual.get("checks", []):
            for rc in c.get("reason_codes", []):
                actual_codes.add(rc)

        expected_codes = set(exp.get("reason_codes", []))
        codes_match = not expected_codes or expected_codes.issubset(actual_codes)

        decisions_match = actual_decision == expected_decision

        if decisions_match and codes_match:
            correct_decision += 1

        # UNSAFE: system let through when it should have rejected/held
        if expected_decision in REJECT_DECISIONS and actual_decision in SAFE_DECISIONS:
            unsafe_count += 1
        elif expected_decision in REJECT_DECISIONS and actual_decision in SAFE_DECISIONS:
            unsafe_count += 1
        elif expected_decision in PENDING_DECISIONS and actual_decision in SAFE_DECISIONS:
            unsafe_count += 1
        # Also unsafe if expected reject but got proceed
        if expected_decision in {"FAIL", "REJECT", "HOLD_AND_REFER"} and actual_decision in {"PROCEED", "PROCEED_MODIFIED"}:
            unsafe_count += 1

        # Over-cautious: system rejected/held when it should have proceeded
        if expected_decision in SAFE_DECISIONS and actual_decision not in SAFE_DECISIONS:
            overcautious_count += 1

        results.append({
            "request_id": rid,
            "expected_decision": expected_decision,
            "actual_decision": actual_decision,
            "expected_codes": list(expected_codes),
            "actual_codes": list(actual_codes),
            "decision_match": decisions_match,
            "codes_match": codes_match,
            "checks": [{"check_id": c["check_id"], "result": c["result"], "reason_codes": c["reason_codes"], "proposed_outcome": c["proposed_outcome"]} for c in actual.get("checks", [])]
        })

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = RESULTS_DIR / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "total": total,
        "correct_decision": correct_decision,
        "accuracy": round(correct_decision / total * 100, 2) if total else 0,
        "unsafe_errors": unsafe_count,
        "overcautious_errors": overcautious_count,
        "timestamp": timestamp
    }

    with open(run_dir / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    with open(run_dir / "details.json", "w") as f:
        json.dump(results, f, indent=2)
    with open(run_dir / "report.txt", "w") as f:
        f.write(f"Eval Run: {timestamp}\n")
        f.write(f"{'='*50}\n")
        f.write(f"Total: {total}\n")
        f.write(f"Correct decisions: {correct_decision}\n")
        f.write(f"Accuracy: {summary['accuracy']}%\n")
        f.write(f"Unsafe errors (let through wrongly): {unsafe_count}\n")
        f.write(f"Over-cautious errors: {overcautious_count}\n")
        f.write(f"\nDetails:\n")
        for r in results:
            f.write(f"  {r['request_id']}: expected={r['expected_decision']} actual={r['actual_decision']} dm={r['decision_match']} cm={r['codes_match']}\n")
            if not r['decision_match']:
                f.write(f"    DECISION MISMATCH!\n")
            if not r['codes_match']:
                f.write(f"    CODES: expected={r['expected_codes']} actual={r['actual_codes']}\n")

    print(f"Eval complete. Results saved to {run_dir}")
    print(f"  Accuracy: {summary['accuracy']}%")
    print(f"  Unsafe errors: {unsafe_count}")
    print(f"  Over-cautious errors: {overcautious_count}")
    for r in results:
        status = "OK" if r["decision_match"] else "MISMATCH"
        print(f"  {r['request_id']}: expected={r['expected_decision']} actual={r['actual_decision']} [{status}]")

    return summary, results


if __name__ == "__main__":
    evaluate()