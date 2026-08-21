# 03-01 Contract Coverage: REST ↔ RPC Mapping (PYE-04a / D-11)

Plan: 03-01 (PYE-04a) — `proto/aiengine.proto` gRPC contract seam
Date: 2026-08-01
Source of truth: `proto/aiengine.proto` (repo root, committed at START of Phase 3)

## Purpose

This document proves every Phase 3 REST endpoint maps 1:1 to a proto RPC, satisfying
ROADMAP Phase 3 success criterion 1: "every REST endpoint satisfies its request/response
semantics 1:1 (transport stays REST/JSON + SSE in v1)". Transport in v1 is REST/JSON + SSE;
the proto is the frozen contract seam (D-11) — no gRPC runtime, no codegen, zero changes to
`backend/internal/ai/engine/*` (Go seam frozen, T-03-01-02).

## Mapping Table

| REST endpoint | proto rpc | request message | response message | status |
|---|---|---|---|---|
| POST /v1/chat | Chat | ChatRequest | ChatResponse | Go seam calls today |
| POST /v1/chat/stream | ChatStream | ChatRequest | stream EngineEvent | Go seam calls today |
| GET /v1/health | (health, unauthenticated) | — | — | out of proto scope (container healthcheck) |
| GET /v1/providers | (operational status) | — | — | out of proto scope (D-10; INT-02 reads it via REST) |
| POST /v1/embed | Embed | EmbedRequest | EmbedResponse | Phase 3 plan 03-04 |
| POST /v1/extract | Extract | ExtractRequest | ExtractResponse | Phase 3 plan 03-05 |
| POST /v1/documents | IngestDocument | IngestDocumentRequest | IngestDocumentResponse | Phase 3 plan 03-05 |
| POST /v1/search | Search | SearchRequest | SearchResponse | Phase 3 plan 03-06 |

## Deliberately Excluded Ops Endpoints

The two operational endpoints (`GET /v1/health`, `GET /v1/providers`) are deliberately NOT
proto RPCs — they are infrastructure/ops surface, not domain calls:

- `GET /v1/health` — unauthenticated container healthcheck (compose urllib healthcheck target);
  no domain semantics.
- `GET /v1/providers` — operational provider status (D-10: TTL-cached health + cooldowns);
  consumed by Go INT-02 via REST only; no request/response domain contract needed.

## EngineEvent SSE Wire Contract (D-02)

What `ChatStream` must emit on the wire (implemented by plan 03-03):

- Each event is exactly one `data:` line whose payload is the JSON envelope
  `{"type":"delta|citation|usage|error|done","data":{...}}` (matches Go `EngineEvent` at
  `backend/internal/ai/engine/engine.go:20-23`).
- Compact JSON, single line — `json.dumps(obj, separators=(",", ":"), ensure_ascii=True)`;
  no literal newlines inside `data` (Go scanner splits on blank lines).
- Event boundaries on blank lines (`\n\n`).
- Heartbeats as comment lines `: ping` every ≤30s (ROADMAP criterion 2).
- No gzip on `text/event-stream`; `Cache-Control: no-cache`, `X-Accel-Buffering: no` headers.

## Field-Semantics Cross-Checks (key_links)

- `POST /v1/chat` → `rpc Chat`: request/response messages match `ChatRequest`/`ChatResponse`
  exactly (D-11). Go's `json.Decoder` ignores unknown fields, so Python MAY add `usage`
  (locked into proto `Usage`; normalized on every response per ROADMAP criterion 2).
- `POST /v1/chat/stream` → `rpc ChatStream`: server-streaming `EngineEvent` envelope matching
  Go `engine.go:20-23` (D-02).
- `POST /v1/documents` → `rpc IngestDocument`: `document_path` + `schema_name` fields match
  (D-09 tenant header semantics — Python validates `^school_[0-9]+$` + existence before any
  DB access, no global fallback).

## Validation

- `protoc` NOT installed on this host → structural grep validation (plan-approved fallback):
  - `syntax = "proto3"` present
  - `service AiEngine` present
  - all six `rpc Chat(`, `rpc ChatStream(`, `rpc Embed(`, `rpc Extract(`, `rpc IngestDocument(`,
    `rpc Search(` present
  - `grep -c "rpc "` == 6
  - 16 messages, file byte-exact with plan's specified content
- Result: VALID (structural; full descriptor build requires protoc at a later gRPC runtime step).
