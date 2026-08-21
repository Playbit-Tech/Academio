---
phase: 01-foundation
reviewed: 2026-07-31T22:55:00Z
depth: standard
files_reviewed: 24
files_reviewed_list:
  - ai-engine/app/config.py
  - ai-engine/app/__init__.py
  - ai-engine/app/main.py
  - ai-engine/Dockerfile
  - ai-engine/.dockerignore
  - ai-engine/.gitignore
  - ai-engine/Makefile
  - ai-engine/pyproject.toml
  - ai-engine/.python-version
  - ai-engine/README.md
  - ai-engine/tests/__init__.py
  - ai-engine/tests/test_health.py
  - ai-engine/uv.lock
  - backend/docker-compose.yml
  - backend/.env.example
  - backend/internal/ai/config.go
  - backend/internal/ai/engine/client.go
  - backend/internal/ai/engine/client_test.go
  - backend/internal/ai/engine/engine.go
  - backend/internal/ai/engine/sse.go
  - backend/internal/ai/engine/sse_test.go
  - backend/internal/config/config.go
  - backend/internal/config/config_test.go
  - .github/workflows/ai-engine.yml
findings:
  critical: 0
  warning: 2
  info: 13
  total: 15
status: issues
---

# Phase 01: Code Review Report

**Reviewed:** 2026-07-31T22:55:00Z
**Depth:** standard
**Files Reviewed:** 24
**Status:** issues_found

## Summary

Phase 1 (Foundation) review of the AI Platform skeleton: the new Python FastAPI service (`ai-engine/`), the Go `EngineClient` seam (`backend/internal/ai/engine/`), backend config additions (`AI_ENGINE_URL`/`AI_ENGINE_TOKEN` fail-fast), docker-compose wiring, and the root CI workflow.

Overall this is a well-structured, defensive first phase. The seam is transport-abstracted (interface-first, gRPC-ready), error wrapping follows Rule B1 everywhere, request contexts propagate per Rule B2, per-endpoint timeouts are sensible (including the deliberate no-timeout design for `ChatStream`), the service-token auth on the engine is fail-closed (an unset token rejects all requests rather than allowing them), and `.env`/secrets are correctly excluded from both git and the Docker build context. Test coverage for the Go seam and config validation is strong and clearly mapped to requirements.

Two warnings surfaced: (1) `docker-compose.yml` declares `prometheus` → `api` `depends_on: condition: service_healthy` but the `api` service defines no healthcheck, so Prometheus and Grafana can never start; (2) the unconditional AI engine fail-fast in `config.validate()` is enforced on all seven `config.Load()` consumers, including DB migration/seed tooling that never touches the AI engine — breaking the documented `make db-init && make migrate && make seed` flow unless AI vars are present. The remaining items are hardening/robustness suggestions (constant-time token comparison, pinning the `uv:latest` tag, SSE edge cases, trailing-slash URL normalization, CI coverage for the Go side).

## Warnings

### WR-01: Prometheus (and Grafana) can never start — `api` service has no healthcheck

**File:** `backend/docker-compose.yml:130-132` (api service block: lines 63-94; grafana depends_on: lines 152-154)
**Issue:** The `prometheus` service declares `depends_on: api: condition: service_healthy`, but the `api` service defines no `healthcheck:` at all. Docker Compose never satisfies `service_healthy` for a service without a healthcheck, so `prometheus` will wait forever and `grafana` (which depends on `prometheus` health) will likewise never start. The stack comes up silently degraded — no metrics, no dashboards.
**Fix:** Add a healthcheck to the `api` service (e.g., the existing `/health` route via wget/curl in the backend image, mirroring the other services), or remove the `condition: service_healthy` constraint and use `depends_on: [api]`:
```yaml
  api:
    # ...existing config...
    healthcheck:
      test: ["CMD", "wget", "--spider", "http://localhost:8080/health"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 15s
```

### WR-02: Unconditional AI engine fail-fast breaks DB migration/seed tooling

**File:** `backend/internal/config/config.go:427-437`
**Issue:** `validate()` now unconditionally requires `AI_ENGINE_URL` and `AI_ENGINE_TOKEN` (regardless of `AI_ENABLED`, in all environments). `config.Load()` is called by seven binaries — `cmd/server/main.go:83`, `cmd/migrate-schemas/main.go:39`, `scripts/migrate/main.go:29`, `scripts/seed/main.go:29`, `scripts/seed-demo/main.go:34`, `scripts/migrate-rollback/main.go:46`, and `cmd/copy-tenant-data/main.go:160`. Six of those are DB tooling that never touches the AI engine. The documented reset flow in AGENTS.md (`make db-init && make migrate && make seed`) now fails at startup unless `AI_ENGINE_URL`/`AI_ENGINE_TOKEN` are in the environment — a hard coupling of pure-DB operations to AI service configuration. Developers who previously had a working `.env` (JWT + ENCRYPTION_KEY only) will see an opaque startup failure in `migrate`, which doesn't obviously relate to AI.
**Fix:** Keep the fail-fast for the server binary but scope it away from DB tooling. Options:
1. Move the AI engine validation out of `validate()` into a `ValidateAIEngineSeam()` method invoked only by `cmd/server` (the seam is only used at runtime, never by migrations), or
2. Introduce a `Config` field such as `SkipAIValidation bool` set by migration/seed entrypoints, or
3. If the fail-fast truly must be global, at minimum surface a clear message in the migrate/seed tools and update AGENTS.md/.env.example so the requirement is discoverable.

Also confirm the product intent: an `AI_ENABLED=false` deployment (e.g., free/basic-only tenants) is still hard-required to run the ai-engine service, since validation is not gated on `AI.Enabled`.

## Info

### IN-01: Service token compared with `!=` (non-constant-time)

**File:** `ai-engine/app/main.py:9`
**Issue:** `x_ai_engine_token != settings.AI_ENGINE_TOKEN` is not constant-time, enabling a theoretical timing side-channel on the shared service token. Low practical risk (internal S2S, high-entropy token), but the fix is trivial. Keep the existing fail-closed guard — a naive `compare_digest` swap alone would allow an empty token + empty header to authenticate when the token is unset.
**Fix:**
```python
import secrets

def require_token(x_ai_engine_token: str | None = Header(default=None)) -> None:
    if not settings.AI_ENGINE_TOKEN or not secrets.compare_digest(x_ai_engine_token or "", settings.AI_ENGINE_TOKEN):
        raise HTTPException(status_code=401, detail="invalid service token")
```

### IN-02: Dockerfile pulls `uv:latest` — non-reproducible build

**File:** `ai-engine/Dockerfile:3`
**Issue:** `COPY --from=ghcr.io/astral-sh/uv:latest` floats; the image content changes whenever uv publishes. CI pins `setup-uv` to a commit SHA (`ai-engine.yml:27`), but the Docker image build does not — a reproducibility inconsistency.
**Fix:** Pin the tag, e.g. `COPY --from=ghcr.io/astral-sh/uv:0.8.10 /uv /uvx /bin/` (match the version CI's SHA corresponds to), or read the version from a single source.

### IN-03: `redis_data` volume declared but never mounted

**File:** `backend/docker-compose.yml:22-32, 158`
**Issue:** `redis_data` is declared in the top-level `volumes:` block but the `redis` service has no `volumes:` mount. Redis state (asynq queue tasks under retry, delayed tasks) is lost on every container recreation, and the declared volume is dead config.
**Fix:** Mount it: `volumes: - redis_data:/data` on the `redis` service.

### IN-04: Obsolete `version: "3.9"` top-level key

**File:** `backend/docker-compose.yml:1`
**Issue:** The `version` key is ignored (with a warning) by Compose v2 and is slated for removal. Dead config.
**Fix:** Delete the line.

### IN-05: Qdrant healthcheck assumes `curl` exists in the image — verify

**File:** `backend/docker-compose.yml:43-48`
**Issue:** The healthcheck runs `curl -f http://localhost:6333/health`. The official `qdrant/qdrant` image does not guarantee `curl` — Qdrant's own docker-compose examples use a bash `/dev/tcp` healthcheck precisely because of this. If `curl` is absent the service is reported unhealthy and `depends_on` chains stall.
**Fix:** Verify `curl` exists in the pinned image; if not, use a `bash -c 'exec 3<>/dev/tcp/127.0.0.1/6333 ...'` style probe or drop the healthcheck.

### IN-06: `baseURL` trailing slash not normalized — double-slash paths

**File:** `backend/internal/ai/engine/client.go:143`
**Issue:** `http.NewRequestWithContext(ctx, method, c.baseURL+path, ...)` concatenates directly. A configured `AI_ENGINE_URL=http://ai-engine:8000/` (trailing slash) produces `http://ai-engine:8000//v1/chat`; most routers tolerate it, but it's fragile.
**Fix:** Normalize in `NewClient`: `baseURL = strings.TrimRight(baseURL, "/")`.

### IN-07: Non-200 responses discard the body — hard to diagnose engine failures

**File:** `backend/internal/ai/engine/client.go:56-58` (also 82-84, 109-111, 131-133)
**Issue:** On a non-200, the response body is never read, so the error is only `"engine chat: unexpected status 502"` — no engine-side error detail (e.g., a JSON `{"detail": "..."}` from FastAPI) survives for logging.
**Fix:** Read a bounded slice of the body (e.g., `io.ReadAll(io.LimitReader(resp.Body, 4096))`) into the error message.

### IN-08: `ChatStream` has no response-header timeout

**File:** `backend/internal/ai/engine/client.go:66-91`
**Issue:** `ChatStream` deliberately has no context deadline (correct — stream lifetime is caller-bound), but the default `http.Transport` has `ResponseHeaderTimeout: 0`. If the engine accepts the connection and then stalls before sending headers, `client.Do` blocks until the caller cancels — a hung engine can pin a handler goroutine indefinitely.
**Fix:** Set `Transport.ResponseHeaderTimeout` (e.g., 30s) on the client used for streams while leaving the body phase unbounded, or accept the risk and document it. The `Chat`/`Extract`/`Health` paths are covered by their ctx deadlines.

### IN-09: SSE parser edge cases — bare `\r` boundaries and empty `data:` events

**File:** `backend/internal/ai/engine/sse.go:40-54, 58-78`
**Issue:** `splitSSEEvent` only recognizes `\n\n` and `\r\n\r\n` boundaries; the SSE spec also requires treating a bare `\r` as a line terminator, so a `\r`-delimited stream would not split until EOF. Additionally, `parseSSEBlock` drops a block containing only `data:` (empty payload), which the spec treats as a valid empty event, and `TrimSpace` on the data payload strips legitimate trailing whitespace. Low risk today — we control the peer — but the parser is the contract boundary for future third-party engines.
**Fix:** Normalize line endings per spec and only strip the single leading space after the field separator, or document these deviations in the package.

### IN-10: Test fixture mutates the module-level settings singleton and never restores it

**File:** `ai-engine/tests/test_health.py:17`
**Issue:** The `settings` fixture assigns `app_settings.AI_ENGINE_TOKEN` (global state) and never restores the prior value. It is deterministic today, but any future test that depends on the default (empty) token — or parallel tests — becomes order-sensitive.
**Fix:** Use `monkeypatch.setattr(app_settings, "AI_ENGINE_TOKEN", s.AI_ENGINE_TOKEN)` (auto-restored) instead of direct assignment.

### IN-11: Go side of the seam has no CI coverage

**File:** `.github/workflows/ai-engine.yml` (whole file)
**Issue:** The repo's only workflows are `ai-engine.yml` and `docs.yml` — there is no Go test workflow. The new `backend/internal/ai/engine/*_test.go` and `backend/internal/config/config_test.go` suites run only locally. Additionally, this workflow's `paths:` filter (`ai-engine/**`) means Go changes to the seam never trigger it.
**Fix:** Add a Go job (or a dedicated backend workflow) running `go test ./internal/ai/... ./internal/config/...`, and either add `backend/internal/ai/**` + `backend/internal/config/**` to the paths or rely on the backend workflow.

### IN-12: ai-engine has no `.env.example` and README omits the token

**File:** `ai-engine/README.md` (whole file); `ai-engine/app/config.py:5`
**Issue:** The engine reads `AI_ENGINE_TOKEN` but there is no `ai-engine/.env.example`, and the README's Bootstrap section never mentions the token. A developer running the engine standalone gets an opaque 401 on every `/v1/*` call (fail-closed) with no indication why.
**Fix:** Add `ai-engine/.env.example` (`AI_ENGINE_TOKEN=`) and one line in the README: "Set `AI_ENGINE_TOKEN` to the same value configured in the backend's `AI_ENGINE_TOKEN`."

### IN-13: Engine does not fail fast at startup when the token is missing

**File:** `ai-engine/app/config.py:5`
**Issue:** The backend fail-fasts when `AI_ENGINE_TOKEN` is missing (Rule B12), but the engine starts silently with an empty token and rejects all authenticated traffic at runtime. Misconfiguration should be loud on the engine side too.
**Fix:** Validate at startup (e.g., in a FastAPI lifespan handler or at module import in non-test mode): `if not settings.AI_ENGINE_TOKEN: raise RuntimeError("AI_ENGINE_TOKEN is required")`.

---

_Reviewed: 2026-07-31T22:55:00Z_
_Reviewer: gsd-code-reviewer (standard depth)_
_Depth: standard_
