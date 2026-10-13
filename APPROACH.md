# Approach

## Problem Summary

Validus is the Registrar & Transfer Agent for a set of mutual funds. Its Transaction Compliance
Check (TCC) desk must check purchase, SIP, redemption and change-of-bank requests that cannot go
straight through, against the TCC SOP (v4.1) and any AMC client addendum, before they are processed.
Today a maker opens five screens and the rulebook by hand for every request (about 11 minutes each,
3 minutes for a checker), the SOP changes often and several versions sit in a shared folder, two
makers can reach different outcomes on the same request, and the case log does not record which
document or version a decision relied on.

The task is to build a system that takes the request as received (email text plus attachments,
including scans and the same requests as API payloads in `Data/inbox/requests.json`), runs the
checks the SOP requires, and returns exactly one outcome with reason codes, the documents relied on,
the approval that is required, and a draft reply — deterministically, traceably and safely. Safety
matters more than throughput: an unavailable source is never treated as a pass, and the system never
concludes a transaction is suspicious or reports to FIU-IND (SOP 8.1).

## Technical Approach

A FastAPI service exposes `POST /requests` (one request object in, one response object out) and
`GET /health`. The pipeline is deterministic code with one optional LLM call used only to read
unstructured text; every rule, outcome and reason code is decided in code.

1. **Ingest** (`src/ingest.py`) — decode attachment bytes (base64) and extract text; scanned files
   fall back to text extraction.
2. **Extract** (`src/extract.py`) — pull the facts the checks need (folio, PAN, amount, ARN/EUIN,
   bank account, dates) from the email body and attachments.
3. **Resolve + checks** (`src/checks/`) — the eight checks always run and always appear in the
   response (`NOT_APPLICABLE` when unused):
   `FOLIO_IDENTITY`, `KYC_STATUS`, `THIRD_PARTY_PAYMENT`, `BANK_MANDATE`, `COB_COOLING`,
   `DISTRIBUTOR_CODE`, `MINOR_RULES`, `REFERRAL`. They read the five extracts in `Data/data/`.
4. **Decide** (`src/decide.py`) — apply the SOP 9.2 precedence
   `INVALID_REQUEST > REJECT > HOLD_AND_REFER > PEND > PROCEED_MODIFIED > PROCEED` and set the
   approver from Annexure A.
5. **Reply** (`src/reply.py`) — draft the investor reply with guardrails: no referral/compliance/
   suspicion wording, and no "processed/approved" unless the outcome is `PROCEED`/`PROCEED_MODIFIED`.
6. **Contract** (`src/contract.py`) — normalise the response to the exact schema and reject any
   violation at runtime.

### Response contract

The response uses the exact contract names and domains (documented in `notes/contract.md`):

- top-level `outcomes` (not `decision`), `reason_codes`, `human_approval_required` (boolean),
  `approver_role` (`CHECKER` | `OPS_MANAGER` | `null`), `resolved`, `request_type`, `draft_reply`;
- each check uses `check_id` (not `check`);
- `outcomes` / `proposed_outcome` are one of the six SOP 9.1 outcomes only — no `PROCESS`;
- `reason_codes` come from SOP 9.3 only — no invented codes such as `FOLIO_MATCHED`;
- `resolved.folio_no` is `NNNNNNNN/NN` (e.g. `40120238/73`).

`src/contract.py` normalises and validates; `tests/test_contract.py` POSTs every inbox request and
asserts the contract holds.

## AI Tool Usage

Built with OpenCode using the Cadra provider. I used it to read the SOP and the extracts, to draft
the check modules and the decision engine, and to iterate against the eval harness. The LLM is used
at runtime only in the extraction stage (unstructured text → facts); all compliance logic is
deterministic, so behaviour is reproducible and testable. The workflow design deliverable is in
[`FUTURE_WORKFLOW.md`](FUTURE_WORKFLOW.md).

## Trade-offs & Limitations

- Extraction is heuristic with an optional model call; ambiguous text can miss a folio/ARN. The
  checks therefore re-scan the raw email as a fallback and never pass on missing data.
- The five extracts are treated as read-only (`data/` is never modified); a "prepared" copy is used
  only for normalisation.
- The response is normalised to the contract at the edge, so the raw check modules can stay
  readable while the wire format stays strict.
- The eval harness scores the 15 known cases; with more time I would add adversarial cases in
  `eval/cases/` and a checker-sampling workflow.
