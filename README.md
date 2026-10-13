# F1 Capstone Template

Starter repository for the Cadra F1 walking-skeleton capstone. Use OpenCode with the Cadra provider to build your solution, document your approach, and submit a public GitHub repo for evaluation.

## Solution

A FastAPI service that checks mutual-fund requests for the Validus TCC desk and returns one response
object per request.

- `POST /requests` — one request object in (`Data/inbox/requests.json` shape), one response object out.
- `GET /health`.
- Eight checks always run (`FOLIO_IDENTITY`, `KYC_STATUS`, `THIRD_PARTY_PAYMENT`, `BANK_MANDATE`,
  `COB_COOLING`, `DISTRIBUTOR_CODE`, `MINOR_RULES`, `REFERRAL`); one of six SOP 9.1 outcomes and SOP 9.3
  reason codes are returned with the approver and a draft reply.
- The response contract is documented in [`notes/contract.md`](notes/contract.md) and enforced by
  `src/contract.py`; the design write-up is in [`APPROACH.md`](APPROACH.md) and
  [`FUTURE_WORKFLOW.md`](FUTURE_WORKFLOW.md).

```bash
pip install -r requirements.txt
python -m pytest tests/        # 32 tests
python eval/run_eval.py        # scores the inbox cases
uvicorn src.solution:app --port 8000
```

## Prerequisites

- Python 3.11+
- [OpenCode](https://opencode.ai) ≥ 1.17.0
- A Cadra JWT (`CADRA_TOKEN`) from the F1 Setup page
- Your Cadra proxy URL (from the F1 Setup page)

## Setup

1. Clone this repo (or use it as a GitHub template).
2. Set the environment variables (both values come from the F1 Setup page):
   ```bash
   export CADRA_PROXY_URL=<your-proxy-url>   # e.g. https://your-proxy.example.com/v1
   export CADRA_TOKEN=<your-cadra-jwt>
   ```
   `opencode.json` reads both via `{env:…}` — no file edits needed.
3. Install OpenCode if not already installed (see [opencode.ai](https://opencode.ai)).
4. Run OpenCode in this directory:
   ```bash
   opencode
   ```
5. Complete `APPROACH.md` and implement your solution in `src/` (start with `src/solution.py`).
6. Push your work to a **public** GitHub repository.
7. Submit your repo URL on the F1 demo page.

## Python environment (optional)

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Project layout

```
.
├── opencode.json    # Cadra provider config (reads CADRA_PROXY_URL + CADRA_TOKEN from env)
├── APPROACH.md      # Written approach (required for submission)
├── FUTURE_WORKFLOW.md  # Workflow design deliverable
├── ARTEFACT.md      # Written deliverable (case reconciliation report)
├── notes/contract.md  # API response contract
├── src/
│   ├── solution.py  # FastAPI service (POST /requests, GET /health)
│   ├── ingest.py    # Attachment decoding / text extraction
│   ├── extract.py   # Facts from email text and attachments
│   ├── checks/      # The eight checks
│   ├── decide.py    # SOP 9.2 outcome precedence
│   ├── reply.py     # Guarded draft reply
│   └── contract.py  # Contract normalisation + validation
├── eval/            # Eval harness (expected.json, run_eval.py, results/)
├── tests/           # Unit, integration and contract tests
├── Data/            # Read-only data room (inbox, extracts, policies)
└── requirements.txt
```
