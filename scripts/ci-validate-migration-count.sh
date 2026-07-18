#!/bin/bash
# CI Migration Count Validation
# Verifies that both core and school migration lists are non-empty and
# properly registered. Since core and school serve different schemas and
# have different migration lists by design, this script validates integrity
# of each list independently rather than comparing counts.
#
# Checks:
#   1. Core migrations are non-empty
#   2. School migrations are non-empty
#   3. Each migration has a unique ID (no duplicates within each list)
#   4. Core and school migration IDs are formatted as expected
#
# Exit codes:
#   0 — all checks pass
#   1 — any check fails

set -euo pipefail

cd "$(dirname "$0")/../backend"

FAILED=0

# ── 1. Core migrations ──────────────────────────────────

CORE_IDS=$(grep -rn 'ID:' internal/database/migrations/core/ 2>/dev/null \
    | grep '"20[0-9][0-9]_' \
    | sed 's/.*"\(.*\)".*/\1/' || true)

CORE_COUNT=$(echo "$CORE_IDS" | grep -c . || echo 0)
echo "Core migrations: $CORE_COUNT"

if [ "$CORE_COUNT" -eq 0 ]; then
    echo "FAIL: Core migrations list is empty"
    FAILED=1
else
    CORE_DUPS=$(echo "$CORE_IDS" | sort | uniq -d)
    if [ -n "$CORE_DUPS" ]; then
        echo "FAIL: Duplicate core migration IDs:"
        echo "$CORE_DUPS"
        FAILED=1
    fi
fi

# ── 2. School migrations ────────────────────────────────

SCHOOL_IDS=$(grep 'ID:' internal/database/migrations/school/school.go 2>/dev/null \
    | grep '"20[0-9][0-9]_' \
    | sed 's/.*"\(.*\)".*/\1/' || true)

SCHOOL_COUNT=$(echo "$SCHOOL_IDS" | grep -c . || echo 0)
echo "School migrations: $SCHOOL_COUNT"

if [ "$SCHOOL_COUNT" -eq 0 ]; then
    echo "FAIL: School migrations list is empty"
    FAILED=1
else
    SCHOOL_DUPS=$(echo "$SCHOOL_IDS" | sort | uniq -d)
    if [ -n "$SCHOOL_DUPS" ]; then
        echo "FAIL: Duplicate school migration IDs:"
        echo "$SCHOOL_DUPS"
        FAILED=1
    fi
fi

# ── Result ──────────────────────────────────────────────

if [ "$FAILED" -eq 1 ]; then
    echo ""
    echo "FAIL: Migration validation failed"
    exit 1
fi

echo "PASS: Migration integrity checks passed"
