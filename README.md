# Validus TCC Desk — Transaction Compliance Check API

FastAPI service that checks mutual-fund requests for the Validus TCC desk against SOP v4.1 and returns exactly one outcome per request with reason codes, the approver and a draft reply.
One request object in, one response object out — no `items` / `responses` wrapper.

**Live:** https://validus-x-cadra-sufiyan.onrender.com/

Try it in the browser — interactive OpenAPI docs: **`/docs`** (Swagger) and **`/redoc`**. Send a request with `POST /requests`.
Live docs: https://validus-x-cadra-sufiyan.onrender.com/docs

## Setup

```bash
pip install -r requirements.txt
```

Optional but recommended:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

If you use the LLM extraction path, set the key in `.env` (never commit it):

```
GEMINI_API_KEY=...
```

## Prepare data

The service reads the five extracts in `Data/data/` (or `prepared/` if generated). No setup step is
required to read them; they are read-only.

## Run

Reads the port from `PORT` (default `8000`):

```bash
python -m src.solution
```

Then:

- `GET  /health`   → `{"status": "ok"}`
- `POST /requests` → one response object

Example:

```bash
curl -X POST http://localhost:8000/requests \
  -H "Content-Type: application/json" \
  --data @request.json
```

where `request.json` is a single request object in the shape of one item in
`Data/inbox/requests.json`.

## Endpoints

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/health` | — | `{"status": "ok"}` |
| POST | `/requests` | one request object | one response object |
| GET | `/docs` | — | Swagger UI |
| GET | `/redoc` | — | ReDoc |

## Where the rules live

| What | Where |
|---|---|
| Rule content (SOP, addendum) | `Data/policies/` (SOP v4.1, TMF addendum) |
| The eight checks | `src/checks/` |
| Outcome precedence (SOP 9.2) | `src/decide.py` |
| Reply guardrails | `src/reply.py` |
| Response contract (names, codes, outcomes) | `notes/contract.md`, enforced by `src/contract.py` |

## Response fields

Core fields: `request_id`, `request_type`, `resolved`, `outcomes`, `reason_codes`,
`human_approval_required`, `approver_role`, `checks`, `draft_reply`, `trace`.

Extra / supporting response fields:

| Field | Type | Meaning |
|---|---|---|
| `request_type` | string | Classified request type (e.g. `REDEMPTION`, `SIP_REGISTRATION`). |
| `resolved` | object | `folio_no` (`NNNNNNNN/NN`), `amc_code`, `first_holder_pan_masked`, `txn_id`. |
| `reason_codes` | string[] | Aggregated SOP 9.3 reason codes across checks. |
| `human_approval_required` | boolean | Whether a human must approve the outcome. |
| `approver_role` | string \| null | `CHECKER`, `OPS_MANAGER`, or `null`. |
| `draft_reply` | object | `to`, `subject`, `body` — investor reply with guardrails. |
| `trace` | object | `model_calls`, `tools_called`, `documents` — audit trail. |

`checks[]` item fields:

| Field | Type | Meaning |
|---|---|---|
| `check_id` | string | One of the eight check ids. |
| `result` | string | `PASS`, `FAIL`, `UNABLE_TO_VERIFY`, `NOT_APPLICABLE`. |
| `reason_codes` | string[] | SOP 9.3 codes for this check. |
| `proposed_outcome` | string | One of the six SOP 9.1 outcomes. |
| `evidence` | object[] | `source`, `ref`, `value` relied on. |
| `sop_clause` | string | Clause applied. |

## Deploy (Render)

- **Build command:** `pip install -r requirements.txt`
- **Start command:** `uvicorn src.solution:app --host 0.0.0.0 --port $PORT`
- Set `GEMINI_API_KEY` (and `CADRA_PROXY_URL` / `CADRA_TOKEN` if used) as environment variables.

## Test

```bash
python -m pytest tests/      # 32 tests (unit, integration, contract)
python eval/run_eval.py      # scores the inbox cases (15/15 decisions, 0 unsafe)
```
