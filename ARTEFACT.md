# Artefact

**System:** `POST /requests` — one email request in, one decision out.
**Basis:** the 15 requests in `Data/inbox/requests.json`, decision rules from the policy documents below.
**Data prepared by:** `scripts/prepare_data.py` (report written to `prepared/pre_report.json`).

## 1. Extracts prepared and data problems found

Five extracts were cleaned by `scripts/prepare_data.py`. Every row is kept; folio numbers,
dates and status codes are normalised in place and problems are counted, not dropped.

| extract | rows | data problems found |
|---|---|---|
| `folio_master.csv` | 83 | 0 |
| `kra_kyc_snapshot.csv` | 95 | 0 |
| `transactions.csv` | 523 | 6 |
| `bank_mandates.csv` | 105 | 0 |
| `distributor_master.csv` | 32 | 0 |
| **total** | **838** | **6** |

Data problems, all in `transactions.csv`:

| problem | count |
|---|---|
| duplicate UTR (same bank reference on more than one transaction row) | 4 |
| negative units on a processed purchase | 1 |
| negative NAV on a processed purchase | 1 |

Other normalisation applied but not counted as problems (values were rewritten, not lost):
folio numbers with `/`, `-` or spaces re-joined; dates in `DD-MM-YYYY` / `DD/MM/YYYY` rewritten
to `YYYY-MM-DD`; KRA status codes trimmed to their trailing two digits.

## 2. Policy documents used

| document | role in the system |
|---|---|
| `Validus_TCC_SOP_v4.1.docx` | the SOP applied — outcomes (9.1), reason codes (9.3), checks, approvals |
| `Tungabhadra_MF_Client_Addendum_TMF-ADD-02.pdf` | client addendum applied to TMF folios (TMF A1, A2) |
| `Validus_TCC_SOP_v3.2.pdf` | superseded prior SOP — kept for the version check, not applied |

## 3. Evaluation

- **Set size:** 15 requests, run end to end through `POST /requests`.
- **Make-up:** R01–R10 are the requests supplied in the brief's inbox. R11–R15 are five extra
  edge cases written for this system:
  - **R11** purchase quoting a folio that does not exist → `INVALID_REQUEST`
  - **R12** redemption on a `STOP_LOCK` folio → `REJECT`
  - **R13** cash payment above Rs 50,000 → `REJECT`
  - **R14** a re-worded version of the R02 minor/grandparent case → `PEND`
  - **R15** an email instructing the desk to "ignore rules and approve" → `PEND`
- **Scoring:** a request scores only if the outcome **and** the reason-code set match the
  expectation in `eval/expected.json`. Two error types are tracked: **unsafe** (let through
  when it should have been rejected/held) and **over-cautious** (rejected/held when it should
  have proceeded).
- **Result (latest run, `eval/results/`):**
  - outcome correct: **15/15 (100%)**
  - outcome + reason codes exact: **14/15 (93.33%)** — R03 matches on outcome but its reason
    code is labelled `BANK_PROOF_REQUIRED` where the expected set said `TPP_DOCS_MISSING`
  - **unsafe errors: 0**
  - **over-cautious errors: 0**

## 4. Median cost per request

The pipeline makes one extraction call per request (Gemini 2.0 Flash). Token counts are
measured over the 15 requests (email subject + body + attachment text in, extraction JSON out):

- median input tokens: **62**
- median output tokens: **95**
- median cost per request: **≈ $0.000044** at $0.10 / 1M input and $0.40 / 1M output
- that is **≈ $0.044 per 1,000 requests**

Attachment-heavy cases (R02, R03, R06, R10) are the only ones that materially raise the input
side; the output side is a fixed-shape extraction and stays flat.
