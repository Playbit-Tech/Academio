---
gsd_project_version: 1.0
name: "SchoolCare Database Transformation"
milestone: v2.0
status: planning
started: 2026-06-30
---

# SchoolCare Database Transformation (v2.0)

## Vision
Transform SchoolCare's database architecture from hybrid SQL/GORM migrations with uint IDs to a unified GORM-based system with UUID primary keys, enhanced base models, and a clean schema foundation.

## Scope

### In Scope
1. **Enhanced BaseModel** — UUID primary keys, audit fields (CreatedBy, UpdatedBy), model interfaces
2. **UUID Migration** — Convert all ~105 model structs from `uint` to `uuid.UUID` IDs
3. **SQL→GORM Conversion** — Replace ~81 raw SQL migrations with GORM AutoMigrate
4. **Fresh Database** — Create new `schoolcare_core` database, run GORM migrations, discard old demo data
5. **API Compatibility Layer** — Accept both UUID and legacy int IDs during transition

### Out of Scope
- AI integration, microservices, distributed systems
- Multi-region deployment or global scaling
- Team/project management staffing (solo + agent workflow)

## Benefits
- **Security** — Non-sequential UUIDs prevent enumeration attacks
- **Maintainability** — Unified GORM migrations replace error-prone SQL
- **Clean Slate** — Fresh database without demo data
- **Future-proof** — UUIDs support distributed systems when needed

## Guiding Principles
- One struct at a time, test after each conversion
- API backward compatibility during transition
- No data loss — the old database is preserved as backup
