import sys, json
sys.path.insert(0, '.')
from starlette.testclient import TestClient
from src.solution import app
client = TestClient(app)
with open('Data/inbox/requests.json') as f:
    reqs = json.load(f)
r = [r for r in reqs if r['request_id'] == 'R08'][0]
print('R08 incoming request subject:', r['subject'])
print('R08 body snippet:', r['body'][:200])

import src.solution as sol
data = sol.load_csv_data()
import src.ingest as ingest
import src.extract as extract
email_text = f"Subject: {r['subject']}\nBody: {r['body']}"
ingested = ingest.ingest_attachments([a for a in r.get('attachments', [])])
att_texts = [{"file_name": a.get("file_name", ""), "text": a.get("text", "")} for a in ingested] if ingested else []
extracted = extract.extract(email_text, att_texts)
print('extracted:', json.dumps(extracted, indent=2)[:500])

import re
folio_norm = re.sub(r"[ /\-]", "", extracted.get("folio", ""))
print('folio_norm:', folio_norm)

txn = None
transactions = data.get("transactions", [])
for t in transactions:
    tf = re.sub(r"[ /\-]", "", t.get("folio_no", ""))
    if tf == folio_norm and t.get("status", "").strip() == "PENDING_TCC":
        txn = t
        break
print('matched txn:', json.dumps(txn, indent=2)[:500] if txn else 'None')

from src.solution import classify_request_type
req_type = classify_request_type(r['body'], r['subject'], extracted, txn)
print('req_type:', req_type)

from src.checks import run_all_checks
results, overall, human_approval, resolved, evidence = run_all_checks(r, extracted, data)
print('overall:', overall)
print('resolved:', json.dumps(resolved, indent=2))
for c in results:
    if c['result'] not in ('PASS', 'NOT_APPLICABLE'):
        print(f'  {c["check"]}: {c["result"]} codes={c.get("reason_codes",[])} outcome={c.get("proposed_outcome","")} sop_clause={c.get("sop_clause","")}')