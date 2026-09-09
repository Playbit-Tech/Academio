# Changelog

All notable changes to the Academio monorepo are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

This repository is the parent/orchestration repo — it tracks submodule pointers
(backend, frontend, mobile, ai-engine, academio-emails). See each submodule's
own `CHANGELOG.md` for detailed component changes.

## [Unreleased]

### Changed
- Nothing yet.

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