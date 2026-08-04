---
phase: 06-observability-security-testing
plan: 02
subsystem: security
tags: [pii-masking, aes-256-gcm, audit, schema-gate, fail-fast, retention, pydantic]

# Dependency graph
requires:
  - phase: 05-go-integration-orchestrator
    provides: AI Orchestrator service, ai_usage_log ledger, crypto.Service (AES-256-GCM), audit middleware (B11)
provides:
  - PII masking helpers (MaskContent / MaskContentSize / RedactErrorMessage) — document/prompt content never in logs
  - AISecretCipher — AES-256-GCM encryption primitive for AI provider secrets at rest (AAD-bound)
  - AI_USAGE_LOG_RETENTION_DAYS config + B12 validation (D-09; prune job deferred)
  - Python fail-fast on partial provider config (Azure key/endpoint/deployment must be all-or-none)
  - Malformed-schema 400 no-fallback API test (D-06)
  - MaskContent wired into AI handler upload-failure log path
affects: 06-04 (probes reuse security package), Phase 7 (per-school provider-secret store can use AISecretCipher)

# Tech tracking
tech-stack:
  added: [crypto/sha256 + encoding/hex redaction, pydantic model_validator, httpx ASGITransport API test]
  patterns:
    - "MaskContent returns {len: N, sha256: <hex>} — never the content itself (D-04)"
    - "AISecretCipher wraps crypto.Service with AISecretAAD binding (D-05)"
    - "model_validator(mode=after) fail-fast on partial Azure provider config (Rule B12)"

key-files:
  created:
    - backend/internal/security/pii.go
    - backend/internal/security/pii_test.go
    - backend/internal/security/ai_secrets.go
    - backend/internal/security/ai_secrets_test.go
  modified:
    - backend/internal/config/config.go (AIUsageLogRetentionDays + validation)
    - backend/internal/modules/ai/handler.go (MaskContent on upload-failure log)
    - ai-engine/app/config.py (partial-provider fail-fast validator)
    - ai-engine/tests/test_schema.py (malformed-schema 400 no-fallback test)

key-decisions:
  - "Provider keys stay env-injected (D-05); AISecretCipher is the encryption primitive for future per-school secret storage — no new DB table this phase"
  - "Python fail-fast implemented as PARTIAL-config detection (Azure all-or-none) rather than requiring every provider key — preserves the Phase 3 'unconfigured providers report unavailable' design while catching misconfiguration"
  - "Malformed-schema 400 test is DB-gated (get_pool runs before the regex gate inside hybrid_search); the regex itself is covered hermetically by test_validate_schema_name_rejects_bad_names"

# Verification
acceptance:
  - "go build ./... in backend/ exits 0"
  - "go test ./internal/security/ ./internal/modules/ai/ ./internal/config/ -count=1 exits 0"
  - "python -m pytest ai-engine/tests/test_config.py ai-engine/tests/test_schema.py -q exits 0 (12 passed, 3 DB-gated skipped)"
  - "Full ai-engine suite: 115 passed, 12 skipped"
  - "grep -c audit backend/internal/modules/ai/handler.go = 7 (>= 6)"
  - "grep MaskContent backend/internal/modules/ai/handler.go exits 0"
  - "grep -nE 'logger\\.(Infof|Warnf|Errorf).*(prompt|content)' handler.go + orchestrator exits 1 (zero raw leaks)"

commits:
  backend: b8a0f4f (feat(security): add PII masking, AI secret encryption, config retention + audit coverage)
  ai-engine: 1a0986e (feat(security): fail-fast partial provider config + malformed-schema 400 test)

# Notes
notes:
  - "Task 1 (pii.go) was started by the gsd-executor subagent before it returned empty; completed and verified inline by the orchestrator"
  - "No new DB table for provider secrets — D-05 keeps keys env-injected; AISecretCipher is ready for Phase 7 per-school secret store"