"""Clean the 5 CSVs into prepared/. Keep all rows and raw values; flag problems."""

import csv
import json
import os
import re
from pathlib import Path
from datetime import datetime

DATA_DIR = Path("Data/data")
PREPARED_DIR = Path("prepared")
PREPARED_DIR.mkdir(exist_ok=True)

def parse_date(val: str) -> str:
    if not val or val.strip() == "":
        return ""
    val = val.strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(val, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return val

def normalise_folio(val: str) -> str:
    if not val:
        return ""
    val = re.sub(r"[ /\-]", "", val.strip())
    return val

def kra_status_last_two(code: str) -> str:
    if not code:
        return ""
    code = code.strip()
    digits = re.sub(r"\D", "", code)
    if len(digits) >= 2:
        return digits[-2:]
    return digits.zfill(2)

def clean_csv(src_name: str, ops: list) -> dict:
    src = DATA_DIR / src_name
    dst = PREPARED_DIR / src_name
    issues = []
    rows = []
    all_utrs = {}
    counters = {"rows": 0, "issues": 0, "duplicate_utrs": 0, "negative_units": 0, "negative_nav": 0}

    with open(src, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        for row in reader:
            counters["rows"] += 1
            r = dict(row)
            for op in ops:
                col = op.get("col")
                if col and col in r:
                    r[col] = op["fn"](r[col])
                    if op.get("flag") and r[col] != row.get(col, ""):
                        issues.append(f"Row {counters['rows']}: {col} normalised '{row.get(col,'')}' -> '{r[col]}'")
            # Duplicate UTR check
            if "utr" in r and r["utr"].strip():
                utr = r["utr"].strip()
                if utr in all_utrs:
                    issues.append(f"Row {counters['rows']}: Duplicate UTR '{utr}' (also row {all_utrs[utr]})")
                    counters["duplicate_utrs"] += 1
                else:
                    all_utrs[utr] = counters["rows"]
            # Negative units/NAV
            if "units" in r and r["units"].strip():
                try:
                    if float(r["units"]) < 0:
                        issues.append(f"Row {counters['rows']}: Negative units '{r['units']}'")
                        counters["negative_units"] += 1
                except ValueError:
                    pass
            if "nav" in r and r["nav"].strip():
                try:
                    if float(r["nav"]) < 0:
                        issues.append(f"Row {counters['rows']}: Negative NAV '{r['nav']}'")
                        counters["negative_nav"] += 1
                except ValueError:
                    pass
            rows.append(r)

    counters["issues"] = len(issues)

    with open(dst, "w", newline="", encoding="utf-8") as f:
        if rows:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    return counters


def main():
    report = {}

    # Folio master
    report["folio_master"] = clean_csv("folio_master.csv", [
        {"col": "folio_no", "fn": normalise_folio},
        {"col": "minor_dob", "fn": parse_date},
        {"col": "opened_on", "fn": parse_date},
        {"col": "contact_last_changed_on", "fn": parse_date},
    ])

    # KRA KYC
    report["kra_kyc_snapshot"] = clean_csv("kra_kyc_snapshot.csv", [
        {"col": "dob", "fn": parse_date},
        {"col": "kra_status_code", "fn": lambda v: v.strip() if v else ""},
    ])

    # Transactions
    report["transactions"] = clean_csv("transactions.csv", [
        {"col": "folio_no", "fn": normalise_folio},
        {"col": "txn_date", "fn": parse_date},
    ])

    # Bank mandates
    report["bank_mandates"] = clean_csv("bank_mandates.csv", [
        {"col": "folio_no", "fn": normalise_folio},
        {"col": "registered_on", "fn": parse_date},
        {"col": "cob_request_received_on", "fn": parse_date},
    ])

    # Distributor master
    report["distributor_master"] = clean_csv("distributor_master.csv", [
        {"col": "arn_valid_till", "fn": parse_date},
        {"col": "euin_valid_till", "fn": parse_date},
    ])

    with open(PREPARED_DIR / "pre_report.json", "w") as f:
        json.dump(report, f, indent=2)

    print(f"Preparation complete. Report written to {PREPARED_DIR / 'pre_report.json'}")
    for k, v in report.items():
        print(f"  {k}: {v['rows']} rows, {v['issues']} issues, {v['duplicate_utrs']} dup UTRs, {v['negative_units']} neg units, {v['negative_nav']} neg NAV")


if __name__ == "__main__":
    main()