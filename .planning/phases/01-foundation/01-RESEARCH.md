# Phase 1: Foundation — Research

**Component:** `ai-engine/` submodule + Go EngineClient seam + docker-compose service + CI
**Researched:** 2026-07-31 (synthesized from verified project research + direct codebase inspection)
**Overall confidence:** HIGH — all stack versions verified against official sources (2026-07-28/30); codebase patterns verified by direct file inspection in this session

## User Constraints

> No CONTEXT.md exists for this phase (no discuss-phase run). Constraints below derive from ROADMAP success criteria and AGENTS.md — treat as locked.

1. **FND-01**: `ai-engine/` FastAPI submodule created (Python 3.13, `pyproject.toml`, dependency bootstrap via uv) — bootstrap from scratch with `uv sync`, start service, passing smoke test, no manual dependency steps.
2. **FND-02**: docker-compose `ai-engine` service added — internal port only (NO published host port), health-checked, mounts the SAME shared uploads volume the `api` service mounts.
3. **FND-03**: Go `EngineClient` seam at `backend/internal/ai/engine/client.go` — HTTP/JSON + SSE, gRPC-ready interface. Per-endpoint timeout budgets: extract = minutes, chat = seconds, stream = no overall cap. `X-Request-ID` propagated on every call.
4. **FND-04**: `AI_ENGINE_URL` + `AI_ENGINE_TOKEN` config — service-to-service auth, NEVER user JWT, NEVER token in URL. Backend fails fast at startup when missing/invalid (Rule B12).
5. **FND-05**: CI for `ai-engine` (ruff lint, pyright type-check, pytest, Docker build) on every push, blocks on failure; existing Go build/lint/test stay green.
6. **Scope boundary (from ROADMAP Phase 1 goal):** The seam, service infrastructure, and CI — NOT the full Python engine (that's Phase 3), NOT pgvector (Phase 2). Python side for Phase 1 = minimal FastAPI skeleton with `/health` + smoke test + service-token middleware scaffold, so the seam can be exercised end-to-end.

## Project Constraints (from AGENTS.md)

- **B1**: No silent error discards — every `err` handled, `%w` wrapping.
- **B2**: No `context.Background()` in request-scoped code — propagate `context.Context` through handler→service→repo→external call chain.
- **B3**: No `fmt.Printf`/`log.Print` — use `pkg/logger` (slog wrapper): `logger.Infof`, `logger.Warnf`, `logger.Errorf`.
- **B4/B13**: No multi-statement `db.Exec()` (pgx v5) — not directly relevant to this phase (no DDL), but note for future.
- **B6**: No hardcoded secrets — all credentials from env, no fallback defaults for secrets.
- **B12**: All config validated at startup — missing/invalid required config fails fast, never silent insecure defaults.
- **Module layout**: `backend/internal/modules/{name}/` = dto.go, handler.go, service.go, repository.go (not applicable to `internal/ai/engine/` which is a seam, but the AI package already exists at `internal/ai/`).
- **Tenancy**: `SchemaTablePrefix` plugin auto-prepends `school_{id}.` for tenant models; `middleware.GetTenantDB(c)` for tenant queries. Not exercised in Phase 1 (no tenant DB work), but the EngineClient must accept `school_id` in requests for future phases.
- **Currency**: NGN/₦ for money display (not relevant to this phase).

## Standard Stack

### Python side (`ai-engine/`)

| Tech | Version | Purpose | Confidence |
|---|---|---|---|
| Python | 3.13.x | Runtime | [VERIFIED: STACK.md research, PyPI 2026-07] |
| FastAPI | 0.140.x | HTTP framework (native SSE since 0.135 — `sse-starlette` obsolete) | [VERIFIED: STACK.md, 0.140.13 on PyPI 2026-07-28] |
| Uvicorn | via `fastapi[standard]` | ASGI server | [VERIFIED: STACK.md] |
| Pydantic | 2.13.x (via FastAPI) | Validation + settings (`pydantic-settings`) | [VERIFIED: STACK.md] |
| uv | 0.7.x | Package/project manager (`pyproject.toml` + `uv.lock`) | [VERIFIED: STACK.md] |
| pytest + pytest-asyncio | 8.x | Testing, `asyncio_mode=auto`, httpx `AsyncClient` | [VERIFIED: STACK.md] |
| ruff | latest | Lint + format | [VERIFIED: STACK.md] |
| pyright | latest | Type checking | [VERIFIED: STACK.md] |

Phase 1 Python scope is deliberately minimal: `pyproject.toml` pinned, FastAPI app with `/health`, service-token dependency, smoke test. Heavy deps (docling, provider SDKs, pgvector) are Phase 3 — DO NOT pull them in Phase 1.

### Go side (backend)

| Tech | Version | Purpose | Confidence |
|---|---|---|---|
| Go | 1.26.1 (`backend/go.mod`) | Runtime | [VERIFIED: go.mod inspection] |
| net/http | stdlib | HTTP client for seam | [VERIFIED: qdrant.go uses `http.Client{Timeout: cfg.Timeout}`] |
| pkg/logger | repo | slog JSON wrapper | [VERIFIED: pkg/logger/logger.go inspection] |
| go.opentelemetry.io/otel | repo | tracing (startSpan/endSpan/recordSpanError in internal/ai/tracing.go) | [VERIFIED: tracing.go inspection] |
| golangci-lint | v1.64.8 (backend CI) | Lint | [VERIFIED: backend/.github/workflows/ci.yml] |

## Architecture Patterns

### 1. Service-to-service seam (the core of this phase)

- **Contract is the Go interface, not the wire protocol** (gRPC-ready): `EngineClient` interface in `backend/internal/ai/engine/client.go` with methods mirroring the future `Provider` shape: `Chat(ctx, req)` JSON, `ChatStream(ctx, req, cb StreamCallback)` SSE, plus `Extract(ctx, req)`. A future `grpcClient` swaps in without touching callers. [VERIFIED: ARCHITECTURE.md Pattern 4]
- **Auth**: service token in header `X-AI-Engine-Token` (NOT Authorization Bearer to avoid confusion with user JWTs; never in URL). Python validates via FastAPI dependency on every route. [VERIFIED: ARCHITECTURE.md — "Service-token auth (AI_ENGINE_TOKEN)"]
- **X-Request-ID**: propagated on every call. Go generates or reads from request context, sends header; Python echoes it back in responses/logs. [CITED: ARCHITECTURE.md + OBS-01 requirement]
- **Timeout discipline**: Go→Python timeout > Python→LLM timeout. Per-endpoint budgets: extract minutes (e.g., 5 min), chat seconds (e.g., 30s), stream no overall cap (context-bound, client disconnect cancels). [VERIFIED: ROADMAP SC3 + ARCHITECTURE.md]

### 2. SSE relay mechanics (needed in Phase 4, scaffold types now)

Five production-proven rules [VERIFIED: ARCHITECTURE.md Pattern 3, Preto.ai / stream-relay-go patterns]:
1. SSE-aware `bufio.Scanner` with custom split on `\n\n` and buffer > 64KB — never blind `io.Copy`.
2. `http.NewRequestWithContext(r.Context(), ...)` — client disconnect cancels upstream.
3. Bounded channel (cap 64) + writer timeout → abort slow clients, no OOM.
4. In-band `error` events after HTTP 200 (status immutable once sent).
5. Headers: `text/event-stream`, `Cache-Control: no-cache`, `X-Accel-Buffering: no`, heartbeat `: ping\n\n` every 25–30s.

Phase 1 ships the `ChatStream` interface + the SSE-aware reader primitive; the full relay route is INT-01 (Phase 4).

### 3. Config + fail-fast (Rule B12)

- Extend `backend/internal/config/config.go` `AIConfig` struct: add `EngineURL string \`env:"AI_ENGINE_URL"\``, `EngineToken string \`env:"AI_ENGINE_TOKEN"\`` (pattern verified at config.go:98-110, getEnv at 304-316).
- Add validation in `validate()` (config.go:404): if `AI_ENGINE_URL` empty → error; if `AI_ENGINE_TOKEN` empty → error. Mirror existing style: `return fmt.Errorf("AI_ENGINE_URL must be set...")`.
- Extend `backend/internal/ai/config.go` `AIServiceConfig` + `FromAppConfig` to carry EngineURL/EngineToken.
- `.env` (backend/.env): add `AI_ENGINE_URL=http://localhost:8000` and `AI_ENGINE_TOKEN=` (dev value), matching existing commented AI_* block style.

### 4. docker-compose (backend/docker-compose.yml)

- Add `ai-engine` service: build context `../ai-engine` (compose file lives in `backend/`, submodule at repo root — verify relative path), `container_name: academio-ai-engine`.
- **No `ports:` mapping** — internal network only (FND-02 requirement b). Compose default network provides inter-service DNS by service name.
- Healthcheck: `test: ["CMD", "curl", "-f", "http://localhost:8000/health"]` (pattern matches gotenberg/qdrant healthchecks; requires curl in image) with start_period.
- Volume: mount the SAME `uploads_data` volume (api mounts `uploads_data:/app/uploads` at compose line 92; volume declared line 141). ai-engine mounts `uploads_data:/app/uploads`.
- `depends_on: api: condition: service_healthy` optional; not strictly needed in Phase 1.
- Env: `AI_ENGINE_URL` not needed inside container; set `APP_ENV`, and (for dev) the token matching backend's `.env` value.

### 5. CI workflow

- Root repo: new `.github/workflows/ai-engine.yml` — triggers on push/PR (paths: `ai-engine/**`), jobs: ruff (`uvx ruff check .`), pyright (`uv run pyright`), pytest (`uv run pytest`), docker build (`docker build -t ai-engine .`). Pattern from docs.yml (root) + backend ci.yml (Go jobs stay in backend submodule repo).
- **Existing Go CI stays green**: backend is a separate git submodule (git@github.com:Playbits/Academio-be.git) with its own `.github/workflows/ci.yml` — Go changes are additive (new package `internal/ai/engine/` + config fields), no breaking changes.

## Don't Hand-Roll

| Problem | Use | Why |
|---|---|---|
| Python packaging/env | uv | 2026 standard; pip/venv/poetry slower, don't manage Python versions |
| SSE in Python | FastAPI native `EventSourceResponse` | Native since 0.135; sse-starlette obsolete |
| SSE parsing in Go | `bufio.Scanner` custom split | Hand-rolled byte parsing is buggy (chunk-boundary corruption) |
| Go HTTP client | `net/http` stdlib + `http.Client{Timeout: ...}` | Matches existing qdrant.go pattern; no new dep |
| Logging | `pkg/logger` (slog JSON) | Rule B3 — no fmt.Printf |
| Tracing | OTel via existing `internal/ai/tracing.go` helpers | Match existing AI package convention |
| Python testing | pytest + httpx AsyncClient | FastAPI current standard |

**DO NOT pull in Phase 1** (they are Phase 3 scope): docling, anthropic/openai SDKs, pgvector/psycopg, prometheus-fastapi-instrumentator, structlog, tiktoken, orjson. Keep the submodule skeleton lean.

## Common Pitfalls

1. **Token in URL** (`?token=...` or `?api_key=...`) — logs leak secrets. Mitigation: header-only auth, verified in tests. [VERIFIED: ROADMAP SC4 + ARCHITECTURE.md]
2. **No timeout on Go http.Client** — a hung Python service hangs the API forever. Mitigation: per-endpoint timeouts (extract 5m, chat 30s), checked in code review + tests. [VERIFIED: ARCHITECTURE.md pitfalls — bare http.Client]
3. **Published port on ai-engine** — defeats internal-network isolation. Mitigation: no `ports:` in compose; verify with `docker compose config`. [VERIFIED: FND-02 requirement b]
4. **Missing healthcheck** — compose won't know service is ready; orchestrator/CI flakiness. Mitigation: `/health` + compose healthcheck with start_period. [VERIFIED: FND-02 requirement a]
5. **`context.Background()` in request path** — cancellation doesn't propagate; token leak on disconnect (Rule B2). Mitigation: always `http.NewRequestWithContext(ctx, ...)`.
6. **Config silent defaults for secrets** (Rule B6/B12) — `AI_ENGINE_TOKEN` must have NO default; empty = startup error.
7. **Volume mismatch** — ai-engine mounting a different volume than api breaks file-passing by path (future PIP-01). Mitigation: same named volume `uploads_data`, same mount path `/app/uploads`. [VERIFIED: ARCHITECTURE.md Pattern 5 — shared uploads volume]
8. **uv.lock drift / non-pinned pyproject** — "works on my machine" bootstrap failures. Mitigation: commit `uv.lock`; CI runs `uv sync` from clean checkout. [VERIFIED: ROADMAP SC1]
9. **SSE buffer default 64KB** — event boundaries at chunk boundaries. Mitigation: custom scanner buffer (e.g., 1MB) in the relay primitive. [VERIFIED: ARCHITECTURE.md Pattern 3]

## Code Examples

### Go EngineClient skeleton (backend/internal/ai/engine/)

```go
// Package engine provides the Go↔Python AI engine seam.
package engine

import (
    "context"
    "net/http"
    "time"
)

// StreamCallback receives parsed SSE events from the engine.
type StreamCallback func(event EngineEvent) error

// EngineEvent is the shared SSE envelope (Phase 4 defines full shape).
type EngineEvent struct {
    Type string          `json:"type"` // delta | citation | usage | error | done
    Data json.RawMessage `json:"data"`
}

// EngineClient is the seam. gRPC-ready: a future grpcClient implements
// the same interface; callers never see transport.
type EngineClient interface {
    Chat(ctx context.Context, req ChatRequest) (*ChatResponse, error)
    ChatStream(ctx context.Context, req ChatRequest, cb StreamCallback) error
    Extract(ctx context.Context, req ExtractRequest) (*ExtractResponse, error)
    Health(ctx context.Context) error
}

// httpClient implements EngineClient over REST/JSON + SSE.
type httpClient struct {
    baseURL    string
    token      string
    httpClient *http.Client // per-endpoint timeouts via request ctx
}

func NewClient(baseURL, token string) EngineClient {
    return &httpClient{
        baseURL: baseURL,
        token:   token,
        httpClient: &http.Client{ /* no global timeout; per-call ctx */ },
    }
}

// Chat posts to /v1/chat with X-AI-Engine-Token + X-Request-ID headers.
func (c *httpClient) Chat(ctx context.Context, req ChatRequest) (*ChatResponse, error) {
    body, _ := json.Marshal(req)
    hreq, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+"/v1/chat", bytes.NewReader(body))
    if err != nil { return nil, fmt.Errorf("engine chat: %w", err) }
    hreq.Header.Set("Content-Type", "application/json")
    hreq.Header.Set("X-AI-Engine-Token", c.token)
    hreq.Header.Set("X-Request-ID", requestIDFromContext(ctx))
    // ... do, decode, wrap errors (Rule B1)
}
```

### Python skeleton (ai-engine/app/)

```python
# app/main.py — Phase 1 skeleton (no heavy deps)
from fastapi import FastAPI, Depends, HTTPException, Header

app = FastAPI(title="Academio AI Engine")

def require_token(x_ai_engine_token: str | None = Header(default=None)) -> None:
    expected = settings.AI_ENGINE_TOKEN
    if not expected or x_ai_engine_token != expected:
        raise HTTPException(status_code=401, detail="invalid service token")

@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "ai-engine"}

@app.get("/v1/health", dependencies=[Depends(require_token)])
async def v1_health() -> dict:
    return {"status": "ok"}
```

### pyproject.toml essentials

```toml
[project]
name = "ai-engine"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = ["fastapi[standard]>=0.140,<0.141"]

[dependency-groups]
dev = ["pytest>=8", "pytest-asyncio", "ruff", "pyright"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

### docker-compose service block

```yaml
  ai-engine:
    build:
      context: ../ai-engine
      dockerfile: Dockerfile
    container_name: academio-ai-engine
    restart: unless-stopped
    # NO ports: — internal network only
    environment:
      AI_ENGINE_TOKEN: "${AI_ENGINE_TOKEN:-local-dev-token}"
    volumes:
      - uploads_data:/app/uploads
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 15s
```

### Config additions (backend/internal/config/config.go)

```go
// In AIConfig struct (after QdrantTimeout):
EngineURL   string `env:"AI_ENGINE_URL"`
EngineToken string `env:"AI_ENGINE_TOKEN"`

// In fromEnv() (after QdrantTimeout line 316):
EngineURL:   getEnv("AI_ENGINE_URL", ""),
EngineToken: getEnv("AI_ENGINE_TOKEN", ""),

// In validate() (after Qdrant-related checks, ~line 404):
if cfg.AI.EngineURL == "" {
    return fmt.Errorf("AI_ENGINE_URL must be set (Go↔Python engine seam)")
}
if cfg.AI.EngineToken == "" {
    return fmt.Errorf("AI_ENGINE_TOKEN must be set (service-to-service auth)")
}
```

*Note: verify the exact `validate()` location and whether AIConfig validation is unconditional or gated on `AI_ENABLED` during implementation — the existing pattern at config.go:507-514 gates key checks on `AI_ENABLED`. The EngineURL/EngineToken check MUST be unconditional (fail-fast per FND-04/SC4) or gated to always-true; decide in the plan and implement accordingly.*

## Validation Architecture

Phase 1 verification is exercised by: Go unit tests for the seam (httptest server mocking Python), Python pytest smoke test (fastapi TestClient / httpx AsyncClient), `docker compose config` validation (no published port), CI green runs, and a manual end-to-end smoke (run both, call /health through the seam). Nyquist VALIDATION.md is disabled for this run (`nyquist_validation: false`).

## Security Notes (for threat_model in plans)

- **Trust boundary**: Go backend → ai-engine (internal Docker network). Token-authenticated.
- **Threats to mitigate in Phase 1**:
  - Token exfiltration via URL/query params (mitigate: header-only, tested)
  - Python endpoints reachable without auth (mitigate: dependency on every route incl. /v1/*; /health may be unauthenticated for container healthcheck)
  - Unbounded connect time / hung upstream (mitigate: per-endpoint timeouts)
  - Secrets with insecure defaults (mitigate: empty default + fail-fast)
  - Published port exposing engine (mitigate: no ports: in compose)
- Python gets NO user-auth surface and NO DB role in Phase 1 — service token only. [VERIFIED: ARCHITECTURE.md trust model]

## References

- [VERIFIED] .planning/research/STACK.md — stack versions, uv, FastAPI 0.140, Python 3.13
- [VERIFIED] .planning/research/ARCHITECTURE.md — seam patterns, SSE relay, service-token auth, trust model, shared volume
- [VERIFIED] .planning/research/SUMMARY.md — "Phase 0: Foundation (seam + infra)" deliverables + pitfalls
- [VERIFIED] Codebase: backend/internal/config/config.go (AIConfig, validate, getEnv), backend/internal/ai/config.go, backend/internal/ai/vector/store.go, backend/internal/ai/tracing.go, backend/pkg/logger/logger.go, backend/docker-compose.yml (uploads_data volume), backend/.github/workflows/ci.yml (submodule), root .github/workflows/docs.yml
