# Artefact — TCC Desk Case Reconciliation Report

**System:** `POST /requests` (one request object in, one response object out)
**Scope:** the requests in `Data/inbox/requests.json` (R01–R15), evaluated as of 9 October 2026
**Rules applied:** Validus TCC SOP v4.1 and the Tungabhadra MF addendum (`Data/policies/`)
**Contract:** `notes/contract.md`; enforced by `src/contract.py`, verified by `tests/test_contract.py`

## 1. Result

Each request receives exactly one of the six SOP 9.1 outcomes with SOP 9.3 reason codes, the resolved
folio/transaction, and the approval required under Annexure A.

| id | type | outcome | reason codes (SOP 9.3) | approver | resolved folio |
|---|---|---|---|---|---|
| R01 | SIP_REGISTRATION | PROCEED | — | none | 40118823/23 |
| R02 | ADDITIONAL_PURCHASE | REJECT | TPP_NO_EXCEPTION, BANK_PROOF_REQUIRED | CHECKER | 40173612/78 |
| R03 | SIP_INSTALMENT | PEND | BANK_PROOF_REQUIRED | none | 71138631/21 |
| R04 | ADDITIONAL_PURCHASE | REJECT | KYC_ON_HOLD | CHECKER | 40120238/73 |
| R05 | NEW_FOLIO_PURCHASE | PEND | KYC_REGISTERED_NEW_AMC | none | — |
| R06 | ADDITIONAL_PURCHASE | PROCEED | — | none | 40159954/10 |
| R07 | ADDITIONAL_PURCHASE | PROCEED | — | none | 40112665/21 |
| R08 | NEW_FOLIO_PURCHASE | PROCEED_MODIFIED | ARN_INVALID_DIRECT | CHECKER | 71167297/25 |
| R09 | ADDITIONAL_PURCHASE | PEND | KYC_UNABLE_TO_VERIFY | none | 40131574/17 |
| R10 | REDEMPTION | HOLD_AND_REFER | BANK_PROOF_REQUIRED, COB_COOLING, HIGH_RISK_CONTACT_COB | OPS_MANAGER | 40115267/30 |
| R11 | ADDITIONAL_PURCHASE | INVALID_REQUEST | FOLIO_NOT_FOUND | none | — |
| R12 | REDEMPTION | REJECT | STOP_LOCK | CHECKER | 40161537/29 |
| R13 | ADDITIONAL_PURCHASE | REJECT | CASH_LIMIT_BREACH | CHECKER | 40138985/28 |
| R14 | NEW_FOLIO_PURCHASE | PEND | ARN_INVALID_DIRECT | none | 71102387/42 |
| R15 | ADDITIONAL_PURCHASE | PEND | BANK_PROOF_REQUIRED | none | 40104822/68 |

## 2. Notable decisions and the clause behind them

- **R02 — REJECT, `TPP_NO_EXCEPTION` (SOP 5.4).** A payment from a grandparent on a minor folio is a
  third-party payment not covered by the related-person exception (withdrawn in v4.1); money is
  refunded to the remitting account.
- **R04 — REJECT, `KYC_ON_HOLD` (SOP 4.4) → CHECKER.** Financial transactions of an investor whose KYC
  is On Hold are not accepted; the reply asks only for KYC to be updated.
- **R05 — PEND, `KYC_REGISTERED_NEW_AMC` (SOP 4.3).** KYC Registered may transact only where a folio is
  already held with the AMC; a fresh KYC is required for the new AMC.
- **R08 — PROCEED_MODIFIED, `ARN_INVALID_DIRECT` (SOP 7.2).** A purchase quoting an invalid ARN is
  processed in the Direct plan of the same scheme and option, no commission payable.
- **R09 — PEND, `KYC_UNABLE_TO_VERIFY` (SOP 4.5).** An unreachable KRA lookup is never treated as a pass.
- **R10 — HOLD_AND_REFER, `BANK_PROOF_REQUIRED`, `COB_COOLING`, `HIGH_RISK_CONTACT_COB` (SOP 6.4, 6.5).**
  A redemption during a change-of-bank cooling period, after a recent contact change, holds the payout
  and refers to the Operations Manager and AMC Compliance. `THIRD_PARTY_PAYMENT` is `NOT_APPLICABLE`
  because a redemption is an outgoing payout with no incoming payment.
- **R11 — INVALID_REQUEST, `FOLIO_NOT_FOUND` (SOP 9.4).** A folio that does not exist in the folio
  master is not substituted with a similar folio.
- **R12 — REJECT, `STOP_LOCK` (SOP 8.4).** No financial transaction is processed on a STOP/LOCK folio;
  only AMC Compliance may lift the lock.
- **R13 — REJECT, `CASH_LIMIT_BREACH` (SOP 8.5).** Cash above Rs 50,000 per investor/AMC/financial year.

## 3. Contract conformance

- Exact names: `outcomes` (not `decision`); `check_id` (not `check`).
- `human_approval_required` is a boolean; `approver_role` is `CHECKER` | `OPS_MANAGER` | `null`.
- Outcomes/proposed outcomes are the six SOP 9.1 outcomes only; reason codes are SOP 9.3 only.
- `resolved.folio_no` is `NNNNNNNN/NN`.
- All eight check ids are always present (`NOT_APPLICABLE` when unused).

## 4. Verification

- `python -m pytest tests/` — 32 passed.
- `python eval/run_eval.py` — 15/15 decisions correct, 0 unsafe errors, 0 over-cautious errors.
