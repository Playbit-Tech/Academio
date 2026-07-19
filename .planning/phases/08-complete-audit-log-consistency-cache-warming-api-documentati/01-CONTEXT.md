# Phase 8 Design Context: Audit Consistency, Cache Warming & API Documentation

**Status:** Context captured (design decisions recorded)
**Created:** 2026-07-19
**Phase:** 8
**Depends on:** None (Phase 7 dependency overridden — Phase 8 is independent and proceeds now)

## Design Decisions

### DD-01: Audit Logging Depth — DEEP

**Decision:** Widen audit middleware + add `LogMutation()` calls in 5 key service layers.

**Rationale:** The middleware infrastructure exists but is scoped to only `tenantAware` routes. `LogMutation()` is defined but never called. A shallow approach (just widen middleware) would miss `ResourceID`, `OldValues`, and `NewValues` — the most valuable audit data.

**Scope:**
1. Apply `AuditLogging` middleware to all `authGroup()` routes (not just `tenantAware`)
2. Add `LogMutation()` calls in these service layers:
   - **User service** — create/update/delete users, role changes, parent assignment
   - **School service** — school config changes, feature toggles
   - **Academic service** — session/term CRUD, curriculum changes
   - **Score service** — bulk score changes, grade item mutations
   - **CBA service** — exam create/update/delete, paper changes
3. Fix `inferResourceType()` heuristic if needed for parameterized routes
4. Add user/school name resolution to `AuditLogResponse` (join on users/schools)

**Out of scope:**
- Adding audit to all 39 modules — only the 5 most impactful
- Frontend audit log viewer (deferred)
- Data retention policy (handled in DD-05)

---

### DD-02: Cache Warming Strategy — COMBINATION

**Decision:** Warm on provisioning + background refresh for active schools.

**Rationale:** `WarmCache()`/`WarmCacheByUUID()` on `TenantResolutionService` are dead code. On provisioning, warming the cache ensures the first request after creation doesn't pay a cold-start penalty. Background refresh keeps frequently used schools warm without reactive latency.

**Scope:**
1. Call `TenantResolutionService.WarmCacheByUUID()` inside provisioning pipeline after migration completes (in `provisioning.go` seed methods or the provisioning task handler)
2. Add a periodic goroutine or cron job (via existing `robfig/cron` from Phase 1) to refresh caches for active schools (e.g., schools with recent activity in last 24h)
3. Keep existing cache-aside pattern as fallback
4. No cache statistics/monitoring in this phase (deferred)

**Out of scope:**
- Distributed cache invalidation for multi-replica (deferred to infrastructure phase)
- Cache hit/miss ratio monitoring

---

### DD-03: Swagger Documentation — COMPLETE

**Decision:** Add annotations to all 10 missing modules + fix inconsistent patterns across all modules + add request body examples + verify with `swag init`.

**Rationale:** Having partial Swagger docs undermines their value for API consumers. A complete pass ensures all endpoints are documented consistently.

**Scope:**
1. Add `@Summary`, `@Description`, `@Security`, `@Produce`, `@Tags`, `@Param`, `@Success`, `@Failure` annotations to all handler methods in these 10 modules:
   - admission, ai, career, conference, discipline, external_exam, lms, parentdashboard, proctoring, studenthealth
2. Fix inconsistent patterns across all ~30 modules:
   - Standardize `@Router` paths to `/api/v2/...` prefix
   - Add `@Failure` annotations where missing
   - Add pagination `@Param` annotations (page, limit) on list endpoints
   - Standardize response model references to `response.APIResponse`
3. Add `@Example` values for request body parameters
4. Run `swag init -g cmd/server/main.go -o cmd/server/docs` and fix all warnings
5. Run `swag init` as part of CI/gating (or document as post-build step)

**Out of scope:**
- Making swagger available in production (dev-only per DD-04)
- Request body examples for every single endpoint (focus on write operations)

---

### DD-04: Swagger in Production — DEV-ONLY

**Decision:** Keep swagger UI behind `Env == "development"` guard.

**Rationale:** Exposing Swagger in production increases attack surface by revealing full API schema. If ops need API reference, they can run the dev server locally or use the generated `swagger.yaml` file directly.

**Scope:**
- No changes to the existing `if cfg.App.Env == "development"` guard

---

### DD-05: Audit Log Retention — ARCHIVE

**Decision:** Move old logs to an archive table (audit_logs_archive) on a scheduled basis.

**Rationale:** Audit logs grow unbounded with no cleanup. Per the deep-audit decision (DD-01), we're adding more logging, making retention more important. Archival preserves data for compliance while keeping the main table fast.

**Scope:**
1. Create `audit_logs_archive` table (same schema as `audit_logs`)
2. Add a cron job (via existing Phase 1 `robfig/cron` infrastructure) that moves logs older than 90 days from `audit_logs` to `audit_logs_archive`
3. The archive table uses the same tenant schema (`school_{id}.audit_logs_archive`) via `SchemaTablePrefix`
4. Admin endpoint to query archive logs (read-only, filtered)

**Out of scope:**
- Automatic deletion of archive logs (retain indefinitely for compliance)
- Compression or storage tiering for archive data

---

### DD-06: Phase Ordering (OVERRIDDEN)

**Decision:** Phase 8 proceeds now, independent of Phase 7.

**Rationale:** Phase 8's work items (audit logging, cache warming, Swagger docs) have no technical dependency on Phase 7 (delivery webhooks, Sentry, monitoring). Deferring was conservative; proceeding unlocks value sooner.

---

### DD-07: Frontend Scope

**Decision:** No frontend work for Phase 8.

**Rationale:**
- Swagger UI already available at `/swagger/index.html` in dev mode (DD-04)
- Audit log viewer is useful but not blocking — deferred to future phase
- Cache warming is entirely backend-infrastructure work

---

## Summary of Work Items (for future planning)

### Backend — Audit
- [ ] Widen `AuditLogging` middleware to all `authGroup()` routes
- [ ] Add `LogMutation()` calls in User, School, Academic, Score, CBA service layers
- [ ] Fix `inferResourceType()` for parameterized routes
- [ ] Add user/school name resolution to `AuditLogResponse`
- [ ] Create `audit_logs_archive` table
- [ ] Add cron job for 90-day log archival
- [ ] Add admin archive query endpoint

### Backend — Cache Warming
- [ ] Call `WarmCacheByUUID()` in provisioning pipeline
- [ ] Add periodic goroutine/cron for active school cache refresh

### Backend — Swagger
- [ ] Add annotations to admission, ai, career, conference, discipline, external_exam, lms, parentdashboard, proctoring, studenthealth
- [ ] Standardize inconsistent annotations across all ~30 existing modules
- [ ] Add request body examples for write operations
- [ ] Run `swag init` and fix all warnings
- [ ] Document `swag init` as post-build step or CI gate

### Frontend
- [ ] None (swagger UI already available in dev mode)
