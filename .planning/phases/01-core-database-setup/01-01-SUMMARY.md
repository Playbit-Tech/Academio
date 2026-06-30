# 01-01: EncryptionService

**Status:** Complete
**Completed:** 2026-06-29

## What was built

- `backend/internal/crypto/encryption.go` — AES-256-GCM encryption service using Go stdlib (`crypto/aes` + `crypto/cipher`)
- `backend/internal/crypto/encryption_test.go` — 7 unit tests
- `backend/internal/config/config.go` — added `EncryptionConfig` with `Key` field, loaded from `ENCRYPTION_KEY` env var

## Key details

- **Encrypt(plaintext, aad)**: Generates 12-byte random nonce via `crypto/rand`, seals with AES-256-GCM, prepends nonce to ciphertext, returns base64-encoded string
- **Decrypt(encoded, aad)**: Base64-decodes, splits nonce + ciphertext, opens with GCM, returns plaintext
- **AAD binding**: School ID passed as Additional Authenticated Data, preventing ciphertext reuse across tenants
- **Key validation**: ENCRYPTION_KEY must be 64 hex chars (32 bytes), validated at startup
- **Convenience methods**: `EncryptString`/`DecryptString` with string-based AAD

## Verification

- `go test ./internal/crypto/ -v -count=1` — 7/7 pass (round-trip, wrong AAD, wrong key, empty key, short key, non-hex key, multiple encryptions different)
- `go build ./...` — zero errors
- `go vet ./internal/crypto/` — no issues
