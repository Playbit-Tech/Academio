---
name: test-engineer
description: 'Write comprehensive tests following TDD principles. Covers positive + negative cases, Arrange-Act-Accert pattern, mocking external dependencies, and running tests before handoff. Use before implementing any new feature or fixing a bug.'
---

# Test Engineer

## Principles

- **Test behavior, not implementation** — what code does, not how
- **AAA Pattern** — Arrange, Act, Assert in every test
- **Positive + negative required** — every behavior needs both success and failure cases
- **Mock externals** — deterministic tests, no real network/DB calls
- **Independent** — no shared state, run in any order

## Workflow

### 1. Understand what to test

Identify:
- Happy path (expected inputs → expected outputs)
- Error cases (invalid inputs, missing data, unauthorized)
- Edge cases (empty, nil, zero, boundary values)
- State transitions (what sequences of calls are valid)

### 2. Write tests

#### Go backend tests

```go
func TestImpersonate_Success(t *testing.T) {
    // Arrange
    // Act
    // Assert
}

func TestImpersonate_Forbidden_NonAdmin(t *testing.T) {
    // Arrange
    // Act
    // Assert
}
```

Mock pattern for Go:
- Use `testify/mock` for service interfaces
- Use `testify/assert` or `testify/require` for assertions
- Use `go-sqlmock` for GORM query verification when needed

#### Frontend tests (Vitest + Testing Library)

```typescript
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";

describe("Component", () => {
    it("renders the expected output", () => {
        // Arrange
        // Act
        // Assert
    });

    it("handles error state", () => {
        // Arrange
        // Act
        // Assert
    });
});
```

### 3. Run tests

```bash
# Backend
cd backend && go test ./internal/modules/... -v -count=1

# Frontend
cd frontend && yarn test

# Integration
cd backend && bash scripts/test_endpoint.sh
```

### 4. Verify coverage

- Critical paths: 100% (auth, impersonation, payments)
- High-value logic: 90%+ (business rules, calculations)
- Utility code: 80%+

## Output format

After writing tests, report:

```
Tests written: [N]
  - Positive: [N]
  - Negative: [N]
  - Edge cases: [N]
All passing: ✅/❌
Coverage: [X]%
```
