# Changelog

All notable changes to the Academio monorepo are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

This repository is the parent/orchestration repo — it tracks submodule pointers
(backend, frontend, mobile, ai-engine, academio-emails). See each submodule's
own `CHANGELOG.md` for detailed component changes.

## [Unreleased]

### Changed
- Bumped frontend `7108f57` → `8f08e40` — super-admin mobile polish: `DataTable` mobile cards, Create School drawer, sticky `/school` tabs with icons/counts, role on mobile user rows, class descriptions, Email Studio external indicator (`8f08e40`).
- Bumped backend `5d08842` → `2119b43` — `golangci-lint` clean: `seeddemo` errcheck handling + unused `nolint` removal (`1ef0b00`, `2119b43`).
- Bumped backend `2119b43` → `e5ae24c` — `country` field for schools (DTOs, location/details merge) + full Lagos, Nigeria address on the demo-seed school (`51d8c42`, `e5ae24c`).
- Bumped backend `e5ae24c` → `f6bf316` — super-admin `PUT /admin/schools/:id` update endpoint (`acad919`, `f6bf316`).
- Bumped backend `f6bf316` → `647ef01` — `devops` lint clean (`647ef01`).
- Bumped backend `647ef01` → `c3d316f` — analytics/AI entitlement, grading scale, embeddings, promotion names, scores aggregation (local only, unpushed).
- Bumped frontend `d7f1ddd` → `218fea5` — shared `SchoolDrawer` + super-admin edit, framework in form, billing `#` index column, `Card` typo fix (`218fea5`).
- Bumped frontend `218fea5` → `1a58731` — `matchMedia` test mock, 347/347 green (`1a58731`).
- Bumped frontend `1a58731` → `451247f` — AI Studio, gating UX, sidebar search, academics hub (local only, unpushed).
- Bumped frontend `451247f` → `f1f6f02` — sticky headers, tab scroll arrows, admin mobile pass.
- Bumped backend `647ef01` → `5c059b7` — prod deploy AI env block.
- Bumped ai-engine `ee574b4` → `bcd9c7a` — CI engine `.env` + service-user ownership fix.

### Fixed
- Nothing yet.

## [1.2.1] - 2026-09-10

### Changed
- Bumped backend `3cdb232` → `71d74c9` — default free-plan enrollment (`28db495`), subscription self-read + schema guard (`04313eb`), Google OIDC `sub` fix (`35c2aa2`), security audit: C1/C2 registration + role scoping (`39d4f08`), H18/H21/H8 fail-fast secrets, Redis AUTH, authenticated uploads (`7d15d31`, `10d2687`), H1/H4 impersonation revoke + refresh-reuse kill (`a1c339b`), H2/H3 TOTP encryption + token strength (`73d494e`), H6/H7/H9 reset oracle, expiry truth, SVG strip (`0ba9eab`), H15 checkout claim-first (`49ddda2`), H19/H23 seed guard + metrics gate (`4ca860e`), M3/M4 authz hardening (`17ca3d5`), M8/L1/L5 rand, HS256 pin, JTI suffix (`501d58f`), M9/M10/M8-api fail-closed gates + list caps (`31e41bc`), M11/M12 cron overlap + webhook ledger gate (`8e8290c`), L3 cipher key-versioning (`83a07fa`), release (`480a112`).
- Bumped frontend `77265c5` → `36cc0f9` — billing i18n/pagination (`08c4ab5`), verify/impersonation/billing labels (`aed8db8`), badges + plan column (`d79b191`), subscription self-read + Turnstile/Firebase CSP (`b144052`, `c6b970d`), push attestation wait (`d8d9f8a`), credentials:include SSO fix (`7b76403`), prod CSP (`54b54ac`), impersonation stop refresh (`363a550`), vercel.json removal (`94132f4`), H17 template text rendering (`a9ceb2c`), M1/M2 dead-session purge + freshness gate (`9cd2c88`), H9/H16 SVG block + no sourcemaps (`649b939`), M6/M8 SW guard + devtools gate (`eee7c11`), L1/L3/M4 env example, autocomplete, safe navigation (`1480d05`), L2 logger routing (`18c64cb`), release (`97df9c2`).

### Fixed
- Nothing yet.

## [1.2.0] - 2026-09-09

### Changed
- Bumped backend to `3cdb232` — v1.1 revenue-critical billing (subscription billing, dunning/gating, application fees, eligibility engine — `cf06184`), remaining 40% (reconciliation report, AI rescore, spelling rename, webhook k6 — `01404ed`), production-review fixes (rescore hardening, report bounds, `4461d0a`; test-fake fidelity, webhook shapes, rollback notes, `056ea9d`), public-admissions tenant resolution + Stripe nested ref (`3cdb232`).
- Bumped frontend to `77265c5` — billing dashboard, fee prompt, eligibility UI (`bd0abf5`), AI score card + behavioral rename (`8745b5a`), rescore detail invalidation (`77265c5`).

### Fixed
- Nothing yet.

## [1.1.0] - 2026-09-08

### Changed
- Bumped backend to `06b8054` — queue dashboard all/failed/processed states, nil-safe email templates with default branding fallback, bounded retries, parent verification + seed fixes.
- Bumped frontend to `ab4c388` — queue dashboard defaults to All, drop completed/processed states, overview Failed/Processed totals.
- Bumped backend + frontend for postgres/redis health enrichment, queue dashboard, async provisioning, SSL posture, and seed fixes.
- Bumped frontend for PWA auto-update + iOS reload fallback.
- Bumped backend for school FK cascade fix (defensive checks).
- Bumped backend + frontend for email-verification gate fixes and lint fixes.
- Bumped backend + academio-emails for email branding (Sage Green, real logo, footer polish).

### Added
- `VERSION` file at repo root (`1.1.0`).

## [1.0.0] - 2026-08-21

Initial production release — foundation, auth, RBAC, curriculum, assessments,
results, finance, communication, and multi-tenant provisioning (phases 01–06).

[Unreleased]: https://github.com/Playbit-Tech/Academio/compare/1.2.0...main
[1.2.0]: https://github.com/Playbit-Tech/Academio/compare/1.1.0...1.2.0
[1.1.0]: https://github.com/Playbit-Tech/Academio/compare/1.0.0...1.1.0
[1.0.0]: https://github.com/Playbit-Tech/Academio/releases/tag/1.0.0