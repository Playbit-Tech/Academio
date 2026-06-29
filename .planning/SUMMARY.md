# Multi-Tenant Database Migration — Plan Summary

## Overview

Six-phase migration transforming SchoolCare v2 from single-database row-level (SchoolID) isolation to database-per-tenant architecture. The migration is backward-compatible, zero-downtime, and builds on the existing sophisticated multi-tenant foundation.

## Requirements Coverage

| ID | Requirement | Phase |
|----|-------------|-------|
| GSD-R1 | EncryptionService (AES-256 for DB credential encrypt/decrypt) | Phase 1 |
| GSD-R2 | Enhance schools table schema + database_connections + tenant_backups tables | Phase 1 |
| GSD-R3 | DatabaseConnectionManager (sync.Map cache, GORM connection pooling, health checks) | Phase 1 |
| GSD-R4 | Repository Factory Pattern (bridge to Phase 2) | Phase 1 |
| GSD-R5 | Make all repositories accept tenant DB connections via factory | Phase 2 |
| GSD-R6 | Update service layer with tenant context injection | Phase 2 |
| GSD-R7 | Tenant context middleware + enhanced auth middleware | Phase 2 |
| GSD-R8 | Core vs school migration directories + MigrationService | Phase 3 |
| GSD-R9 | Tenant migration tools (MigrateAllTenants, parallel migration, status tracking) | Phase 3 |
| GSD-R10 | TenantResolutionService (JWT → tenant DB resolution) | Phase 4 |
| GSD-R11 | Enhanced error handling + tenant-aware logging | Phase 4 |
| GSD-R12 | BackupService (pg_dump, S3 upload, scheduling) | Phase 5 |
| GSD-R13 | RestoreService (point-in-time recovery, validation) | Phase 5 |
| GSD-R14 | Comprehensive integration/load/security testing | Phase 6 |
| GSD-R15 | Documentation + deployment guides | Phase 6 |

**Coverage:** 15/15 requirements mapped ✓

## Phase Summary

| Phase | Goal | Plans | Dependencies |
|-------|------|-------|-------------|
| 1. Core Database Setup | Encryption, schema, connection manager, factory | 4 plans | None |
| 2. Repository Refactoring | All repos tenant-aware via factory | 3 plans | Phase 1 |
| 3. Migration System | Core/school migrations, tenant tools | 3 plans | Phase 2 |
| 4. Enhanced Auth | JWT → tenant DB resolution, error handling | 2 plans | Phase 3 |
| 5. Backup & Recovery | pg_dump + S3, point-in-time restore | 2 plans | Phase 4 |
| 6. Testing & Validation | Integration, load, security, docs | 4 plans | Phase 5 |

**Total plans:** 18

## Key Architectural Decisions

1. **AES-256-GCM** for credential encryption (never plaintext DB passwords)
2. **sync.Map** for in-memory connection cache (no external dependency for hot path)
3. **RepositoryFactory** as DI bridge — keeps existing constructor pattern, adds school ID parameter
4. **Migration directories** split: `migrations/core/` for shared, `migrations/school/` for per-tenant
5. **pg_dump custom format** for backups (compressed, parallel restore capable)
6. **S3** for backup storage (durable, versioned, cross-region)
7. **Tenant context caching** in Redis with TTL to avoid core DB lookup per request
