---
name: code-reviewer
description: 'Review code for correctness, security, and quality with structured severity ratings. Focuses on security vulnerabilities first, then correctness, style, and maintainability. Use before submitting any PR or after making significant changes.'
---

# Code Reviewer

## Workflow

Run these checks in priority order.

### 1. Security scan

Check for:
- Hardcoded secrets, API keys, credentials
- SQL injection vectors (raw queries, string concatenation)
- Command injection (user input in exec/shell calls)
- JWT/authentication weaknesses (missing validation, weak claims)
- CSRF bypasses
- Missing input validation at system boundaries
- Exposed internal implementation details in error messages
- Insecure direct object references (IDOR)
- Rate limiting gaps on auth/impersonation endpoints

### 2. Correctness check

- Function signatures match all call sites
- Error paths are handled (not swallowed or ignored)
- Edge cases are covered (empty lists, nil values, zero IDs, boundary conditions)
- Async operations have proper error propagation
- State transitions are valid (can't go from active to deleted without proper checks)

### 3. Style & conventions

- Follows `backend/STYLE.md` (Go) or project's TypeScript conventions
- Uses `pkg/logger` not `log.Printf` or `console.log`
- Error returns for state mutations; log-and-continue only for best-effort analytics
- No dead code, commented-out code, or debug artifacts
- Imports are clean and organized

### 4. Maintainability

- Functions under 50 lines
- Clear naming — not overly abbreviated
- Comments explain _why_, not _what_
- Single responsibility per function/module
- No duplicated logic

## Output format

```
## Review findings

### 🔴 CRITICAL
- [description with file:line] → fix recommendation

### 🟡 HIGH
- [description with file:line] → fix recommendation

### 🔵 MEDIUM
- [description with file:line] → fix recommendation

### ⚪ LOW
- [description with file:line] → suggestion

## Summary
[count] findings — [X] critical, [Y] high, [Z] medium, [W] low
```
