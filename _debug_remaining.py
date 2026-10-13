import sys, json
sys.path.insert(0, '.')
from starlette.testclient import TestClient
from src.solution import app
client = TestClient(app)
with open('Data/inbox/requests.json') as f:
    reqs = json.load(f)
for rid in ['R02','R07','R13']:
    r = [r for r in reqs if r['request_id'] == rid][0]
    resp = client.post('/requests', json={'items': [r]})
    data = resp.json()['responses'][0]
    print(f'--- {rid}: decision={data["decision"]}')
    for c in data['checks']:
        if c['result'] not in ('PASS','NOT_APPLICABLE'):
            print(f'  {c["check"]}: {c["result"]} codes={c.get("reason_codes",[])} outcome={c.get("proposed_outcome","")}')