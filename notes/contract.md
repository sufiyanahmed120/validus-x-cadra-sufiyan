# TCC Desk API — Response Contract

`POST /requests`
- Request body: **exactly one** request object (the shape of one item in `Data/inbox/requests.json`).
- Response body: **exactly one** response object (no `items` / `responses` wrapper).

## Response object

```
{
  "request_id": "<string>",
  "request_type": "<string>",
  "resolved": {
    "folio_no": "<NNNNNNNN/NN>",
    "amc_code": "<string>",
    "first_holder_pan_masked": "<string>",
    "txn_id": "<string>"
  },
  "outcome": "<one of the six SOP 9.1 outcomes>",
  "reason_codes": [ "<SOP 9.3 code>", ... ],
  "human_approval_required": true | false,          // boolean only
  "approver_role": "CHECKER" | "OPS_MANAGER" | null,
  "checks": [
    {
      "check_id": "<one of the 8 check ids>",
      "result": "PASS" | "FAIL" | "UNABLE_TO_VERIFY" | "NOT_APPLICABLE",
      "reason_codes": [ "<SOP 9.3 code>", ... ],
      "proposed_outcome": "<one of the six outcomes>",
      "evidence": [ { "source": ..., "ref": ..., "value": ... } ],
      "sop_clause": "<clause>"
    },
    ... all 8 check_ids always present ...
  ],
  "draft_reply": { "to": ..., "subject": ..., "body": ... },
  "trace": { "model_calls": [...], "tools_called": [...], "documents": [...] }
}
```

## Rules

- Exact names: `outcomes` (not `decision`), `check_id` (not `check`).
- `human_approval_required` is a **boolean**; `approver_role` is a separate top-level field.
- `outcomes` / `proposed_outcome` are one of the **six** SOP 9.1 outcomes only:
  `PROCEED`, `PROCEED_MODIFIED`, `PEND`, `REJECT`, `HOLD_AND_REFER`, `INVALID_REQUEST`.
  (No `PROCESS`, no `FAIL` as an outcome.)
- `reason_codes` come from SOP 9.3 only:
  `KYC_ON_HOLD`, `KYC_REJECTED`, `KYC_REGISTERED_NEW_AMC`, `KYC_UNABLE_TO_VERIFY`,
  `TPP_NO_EXCEPTION`, `TPP_DOCS_MISSING`, `BANK_PROOF_REQUIRED`, `MINOR_ATTAINED_MAJORITY`,
  `COB_COOLING`, `HIGH_RISK_CONTACT_COB`, `ARN_INVALID_DIRECT`, `EUIN_MISSING`,
  `REFERRAL_TRIGGER`, `STOP_LOCK`, `CASH_LIMIT_BREACH`, `FOLIO_NOT_FOUND`, `FOLIO_PAN_MISMATCH`.
  (No invented codes such as `FOLIO_MATCHED`.)
- `resolved.folio_no` is always in `NNNNNNNN/NN` form (e.g. `40120238/73`).

## Worked case — R10 (redemption)

- `THIRD_PARTY_PAYMENT` = `NOT_APPLICABLE` (a redemption is an outgoing payout; no incoming payment).
- `reason_codes` include `BANK_PROOF_REQUIRED` (redemption during a change of bank) and `COB_COOLING`.
- `outcomes` = `HOLD_AND_REFER`, `human_approval_required` = `true`, `approver_role` = `OPS_MANAGER`.

## Validation

`src/contract.py` normalises every response to this shape and rejects violations at runtime.
`tests/test_contract.py` POSTs every inbox request and asserts the contract holds.
