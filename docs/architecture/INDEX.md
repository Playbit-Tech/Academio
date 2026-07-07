# SchoolCare v3 — Architecture Documentation Index

## Complete Architecture Specification

This directory contains the full architecture specification for evolving SchoolCare from a School ERP into a **modern AI-Powered School Operating System** — while maintaining full backward compatibility with the existing v2 API.

---

### Document Map

| # | Document | Description | Pages |
|---|----------|-------------|-------|
| 1 | [VISION-AND-STRATEGY](./1-VISION-AND-STRATEGY.md) | Product vision, strategic pillars, roadmap, monetization, scaling strategy, competitive landscape | ~15 |
| 2 | [ARCHITECTURE-OVERVIEW](./2-ARCHITECTURE-OVERVIEW.md) | High-level architecture, modular evolution plan, module catalog, folder structure, key decisions | ~12 |
| 3 | [DATABASE-SCHEMA](./3-DATABASE-SCHEMA.md) | ERD, tenancy model, complete table definitions (Admissions, CBA, LMS, Alumni, AI), enum extensions | ~18 |
| 4 | [API-SPECIFICATIONS](./4-API-SPECIFICATIONS.md) | API design principles, full endpoint catalog (25+ modules), event architecture, webhooks | ~14 |
| 5 | [AI-ARCHITECTURE](./5-AI-ARCHITECTURE.md) | AI gateway, RAG engine, agent framework, NL search, cost optimization, implementation structure | ~10 |
| 6 | [SECURITY-INFRASTRUCTURE](./6-SECURITY-INFRASTRUCTURE.md) | Defense-in-depth, auth flow, RBAC/ABAC, audit logging, multi-tenant strategy, Kubernetes, CI/CD, monitoring, mobile API strategy | ~14 |
| 7 | [USE-CASES](./7-USE-CASES.md) | 15 actor personas, 15 detailed use cases with AI extensions, actor×module permission matrix | ~10 |
| 8 | [FUTURE-EXPANSION](./8-FUTURE-EXPANSION.md) | Phase 10+ roadmap, blockchain credentials, crypto payments, metaverse classrooms, go-to-market, KPIs, existing vs evolved comparison | ~10 |
| 10 | [AUDIT-CHECKLIST](./10-AUDIT-CHECKLIST.md) | Production audit checklist: architecture, security, DB, performance, observability, tenant isolation, testing, consistency | ~25 |

---

### Quick Reference

**Core Architecture Decisions:**
- **API Version**: All `/api/v2/` — no v3; new modules added under same prefix
- **Backward Compatibility**: Don't break existing endpoints; additive-only changes
- **Language**: Go (Gin) backend, React 19 (Vite + TanStack Router) frontend
- **Database**: PostgreSQL + Redis (existing) + Qdrant + MinIO + ClickHouse (new)
- **AI**: Multi-provider (OpenAI + Anthropic), RAG with Qdrant, 10+ specialized agents
- **Tenancy**: Shared schema with `school_id` (default); schema-per-tenant (enterprise)
- **Deployment**: Docker → Kubernetes; HPA-ready; OpenTelemetry + Prometheus + Grafana

**Key Principles:**
1. Retain all existing functionality — no removals
2. AI is embedded into every module, not bolted on
3. Complete student lifecycle: Prospect → Applicant → Student → Graduate → Alumni
4. API-first, event-driven, real-time by default
5. Multi-tenant SaaS from day one of architecture
6. 1M+ student scalable design

---

### Implementation Priority

| Phase | Focus | Timeline |
|-------|-------|----------|
| 1A | Architecture hardening (audit, tracing, perf baselines) | Month 1-2 |
| 1B | Admissions & Enrollment module | Month 3-5 |
| 2 | AI Gateway + first 3 agents | Month 4-7 |
| 3 | CBA Engine + LMS | Month 5-8 |
| 4 | Communication Hub + Parent Portal | Month 6-9 |
| 5 | Alumni + Career Guidance | Month 10-13 |
| 6 | BI + Mobile Apps | Month 12-18 |
