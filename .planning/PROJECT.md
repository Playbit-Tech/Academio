---
gsd_project_version: 1.0
name: "SchoolCare Database Transformation"
milestone: v2.0
status: active
started: 2026-06-30
---

# SchoolCare Database Transformation (v2.0)

## Vision

Transform SchoolCare's database architecture from hybrid SQL/GORM migrations with uint IDs to a unified GORM-based system with UUID primary keys, enhanced base models, and clean schema foundation. Additionally, establish a robust multi-tenant database infrastructure with tenant-aware auth, resolution, migration, backup, and recovery.

## What This Is

A production-ready multi-tenant backend infrastructure for SchoolCare v2, combining:
- **Multi-tenant architecture**: Per-school dedicated PostgreSQL databases managed through a shared core database, with AES-256-GCM encrypted credentials, cached connection pooling, and Redis-backed tenant context resolution.
- **UUID identity system**: Dual-ID strategy (uint PK + UUID) flowing end-to-end through models, repositories, JWT tokens, middleware, and response DTOs.
- **Operational tooling**: Parallel tenant migration system, S3 backup/recovery pipeline via Asynq workers, and comprehensive CI/CD with deployment runbooks.

## Core Value

Secure, scalable multi-tenant school management infrastructure that's operationally robust and developer-friendly.

## Requirements

### Validated

- ✓ **GSD-R1** — EncryptionService (AES-256-GCM for DB credential encrypt/decrypt) — v2.0-alpha
- ✓ **GSD-R2** — Enhanced schools table schema (database connection fields, database_connections, tenant_backups tables) — v2.0-alpha
- ✓ **GSD-R3** — DatabaseConnectionManager (sync.Map cache, GORM connection pooling, health checks) — v2.0-alpha
- ✓ **GSD-R4** — Repository Factory Pattern — v2.0-alpha
- ✓ **GSD-R5** — All repositories accept tenant DB connections via factory — v2.0-alpha
- ✓ **GSD-R6** — Service layer with tenant context injection — v2.0-alpha
- ✓ **GSD-R7** — Tenant context middleware + enhanced auth middleware — v2.0-alpha
- ✓ **GSD-R8** — Core/school migration directories + MigrationService — v2.0-alpha
- ✓ **GSD-R9** — Tenant migration tools (MigrateAllTenants) — v2.0-alpha
- ✓ **GSD-R10** — TenantResolutionService (JWT → tenant DB resolution with Redis cache) — v2.0-alpha
- ✓ **GSD-R11** — Enhanced error handling + tenant-aware logging — v2.0-alpha
- ✓ **GSD-R12** — BackupService (pg_dump, S3 upload, retention) — v2.0-alpha
- ✓ **GSD-R13** — RestoreService (point-in-time recovery, validation) — v2.0-alpha
- ✓ **GSD-R14** — Comprehensive integration/load/security testing — v2.0-alpha
- ✓ **GSD-R15** — Documentation + deployment guides — v2.0-alpha
- ✓ **UUID Auth Flow** — schoolUUID in JWT tokens, FindByUUID in AuthRepository — v2.0-alpha
- ✓ **Core Models UUID** — UUID on SchoolConnection, FindByUUID in UserRepository — v2.0-alpha

### Active

- [ ] **Phase 3** — Convert all ~95 remaining model structs to UUID
- [ ] **Phase 4** — SQL→GORM cleanup, fresh database
- [ ] **Phase 5** — API compatibility layer for UUID/int ID coexistence
- [ ] **Phase 6** — Staged rollout, old DB decommissioning

### Out of Scope

- AI integration, microservices, distributed systems
- Multi-region deployment or global scaling
- Team/project management staffing (solo + agent workflow)

## Context

Shipped v2.0-alpha with 85,281 LOC Go (347 files, 41 test files).
Tech stack: Go 1.26, Gin, GORM, PostgreSQL 16, Redis 7, AWS SDK v2, Asynq.
All 15/15 requirements met across 6 phases, 15 plans, 24+ tasks.
Timeline: 8 days (2026-06-22 → 2026-06-30).

## Key Decisions

| Decision | Outcome | Verdict |
|----------|---------|---------|
| AES-256-GCM for DB credential encryption | Implemented in crypto/encryption.go | ✅ Good |
| sync.Map for connection manager cache | Implemented with concurrent-safe access | ✅ Good |
| Dual-ID strategy (uint PK + uuid) | uint PK kept for backward compat, uuid added for new code | ✅ Good |
| ReusableMigrator with configurable table name | Migrator extracted with tableName param | ✅ Good |
| S3-only backup storage | Implemented with MinIO/DO Spaces support via Endpoint config | ✅ Good |
| go-sqlmock for DB-layer tests | Added as dev dependency for backup/restore/tenant tests | ✅ Good |
| 14-backup retention policy | Enforced in BackupService | ✅ Good |
| pgcrypto extension with uuid_generate_v4() | Ensures unique UUIDs at DB level | ✅ Good |
| TenantResolutionService with 5-min Redis TTL | Caches tenant context, graceful degradation | ✅ Good |
| Asynq for async backup/restore workers | Queue-based architecture for long-running ops | ✅ Good |
| 30% coverage threshold in CI | Enforced via GitHub Actions | ✅ Good |

## Benefits

- **Security** — Non-sequential UUIDs prevent enumeration attacks; AES-256-GCM encrypts credentials at rest
- **Scalability** — Per-school databases with connection pooling and Redis caching
- **Maintainability** — Unified GORM migrations, reusable migrator pattern, comprehensive test suite
- **Operational** — Automated backup/restore, parallel tenant migration, deployment runbooks
- **Clean Slate** — Path to fresh database without legacy demo data

## Guiding Principles

- One struct at a time, test after each conversion
- API backward compatibility during transition
- No data loss — old database preserved as backup
- Tenant isolation — each school's data belongs in its own database

---

*Last updated: 2026-06-30 after v2.0-alpha milestone*
