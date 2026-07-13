---
name: context7
description: 'Fetch live, up-to-date documentation for software libraries, frameworks, and APIs via the Context7 API. Use when you need current docs for any external library instead of relying on potentially outdated training data. Covers Go libraries (Gin, GORM, pgx), React/TS (TanStack Router, TanStack Query, Zustand, Zod, shadcn/ui), and hundreds more.'
---

# Context7 — Live Library Documentation

Fetch current documentation for any library via the Context7 API. Always prefer this over training-data knowledge for external packages.

## Usage

### Step 1: Search for library ID

```bash
curl -s "https://context7.com/api/v2/libs/search?libraryName=LIBRARY_NAME&query=TOPIC" | jq '.results[0]'
```

- `libraryName` (required): Library name (e.g. "gin", "gorm", "tanstack router")
- `query` (required): Topic description for relevance ranking

Response includes `id` (library ID for Step 2), `title`, `description`, `totalSnippets`.

### Step 2: Fetch documentation

```bash
curl -s "https://context7.com/api/v2/context?libraryId=LIBRARY_ID&query=TOPIC&type=txt"
```

- `libraryId` (required): The ID from Step 1
- `query` (required): Specific topic
- `type`: `json` or `txt` — use `txt` for readable output

## Quick lookups for this project

### Go backend

```bash
# Gin web framework
curl -s "https://context7.com/api/v2/libs/search?libraryName=gin&query=middleware" | jq '.results[0].id'

# GORM ORM
curl -s "https://context7.com/api/v2/libs/search?libraryName=gorm&query=preloading" | jq '.results[0].id'

# pgx PostgreSQL driver
curl -s "https://context7.com/api/v2/libs/search?libraryName=pgx&query=connection+pool" | jq '.results[0].id'

# golang-jwt
curl -s "https://context7.com/api/v2/libs/search?libraryName=golang-jwt&query=custom+claims" | jq '.results[0].id'
```

### Frontend

```bash
# TanStack Router
curl -s "https://context7.com/api/v2/libs/search?libraryName=tanstack+router&query=beforeLoad" | jq '.results[0].id'

# TanStack React Query
curl -s "https://context7.com/api/v2/libs/search?libraryName=tanstack+react+query&query=mutations" | jq '.results[0].id'

# Zustand
curl -s "https://context7.com/api/v2/libs/search?libraryName=zustand&query=persist+middleware" | jq '.results[0].id'

# Zod
curl -s "https://context7.com/api/v2/libs/search?libraryName=zod&query=validation" | jq '.results[0].id'

# shadcn/ui (Radix-based)
curl -s "https://context7.com/api/v2/libs/search?libraryName=shadcn+ui&query=sheet+component" | jq '.results[0].id'

# React Hook Form
curl -s "https://context7.com/api/v2/libs/search?libraryName=react-hook-form&query=typescript" | jq '.results[0].id'
```

## Tips

- Use `type=txt` for readable plaintext output
- Be specific with `query` for better results
- URL-encode spaces as `+` or `%20`
- No API key required — rate-limited
- Always verify library usage against live docs, especially for recently updated APIs
