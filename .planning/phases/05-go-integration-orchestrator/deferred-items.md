# Deferred Items — Phase 05

Out-of-scope discoveries logged during plan execution (not fixed per scope
boundary rule — pre-existing failures in unrelated modules).

## 05-03 (INT-02: Provider Status Endpoint)

### Pre-existing test failures in unrelated modules

Discovered during 05-03 full-suite verification. **Confirmed pre-existing** —
both fail identically on the 05-02 baseline commit `8eccad2` (before any
05-03 changes). The 05-03 diff touches only `internal/ai`, `internal/modules/ai`,
`internal/middleware`, `internal/services`, `internal/router`, `internal/queue`
— none of these failures are in the changed packages.

| Package | Failing tests | Symptom |
|---|---|---|
| `internal/modules/finance` | `TestCreateAccount_Success`, `TestPayExpense_Success` | nil pointer dereference (panic) in expense/account test path |
| `internal/modules/grading` | `TestCalculateGrade_WAEC_A1/B2/B3/C4/C5_Threshold` | WAEC threshold calculation mismatch |

**Not fixed:** out of scope for 05-03 (AI provider status). Needs a dedicated
plan/owner — likely a finance test-fixture regression (missing setup causing
nil `*gorm.DB`/transaction) and a grading WAEC boundary-value review.
