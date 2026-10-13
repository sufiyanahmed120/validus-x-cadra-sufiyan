import sys, json
sys.path.insert(0, '.')
from starlette.testclient import TestClient
from src.solution import app
client = TestClient(app)
with open('Data/inbox/requests.json') as f:
    reqs = json.load(f)
r = [r for r in reqs if r['request_id'] == 'R08'][0]
resp = client.post('/requests', json={'items': [r]})
data = resp.json()['responses'][0]
print('decision:', data['decision'])
for c in data['checks']:
    print(f'  {c["check"]}: {c["result"]} codes={c.get("reason_codes",[])} outcome={c.get("proposed_outcome","")}')