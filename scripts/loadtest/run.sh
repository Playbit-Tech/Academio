#!/bin/bash
# ──────────────────────────────────────────────────────────────────
# Academio v2 — k6 Load Test Orchestrator
# ──────────────────────────────────────────────────────────────────
# Runs sequential baseline tests, then parallel load tests.
# All results are exported as machine-readable JSON reports.
#
# Prerequisites:
#   - k6 installed at /home/playbit/go/bin/k6 (or on PATH)
#   - Backend running on http://localhost:8080
#
# Usage:
#   ./scripts/loadtest/run.sh              # full test run
#   ./scripts/loadtest/run.sh login        # single endpoint only
#   ./scripts/loadtest/run.sh parallel     # parallel run only
# ──────────────────────────────────────────────────────────────────

set -euo pipefail

K6="${K6_BIN:-/home/playbit/go/bin/k6}"
BASE_URL="${BASE_URL:-http://localhost:8080}"
REPORT_DIR="scripts/loadtest/reports"
SCRIPT_DIR="scripts/loadtest"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$REPORT_DIR"

echo "════════════════════════════════════════════════════════════"
echo "  Academio v2 — k6 Load Test Suite"
echo "  Timestamp: $TIMESTAMP"
echo "  Target:    $BASE_URL"
echo "  k6:        $K6"
echo "════════════════════════════════════════════════════════════"

run_single() {
  local name="$1"
  local script="$2"
  local report="${REPORT_DIR}/${name}.json"

  echo ""
  echo "─── Running: $name ───"
  $K6 run "$script" \
    --summary-export="$report" \
    -e BASE_URL="$BASE_URL" \
    "$@"
  echo "   ✓ Report saved: $report"
}

# ── Argument-based execution ─────────────────────────────────────
if [[ $# -gt 0 ]]; then
  case "$1" in
    login|attendance|scores|users|bills)
      run_single "$1" "${SCRIPT_DIR}/${1}.js"
      exit 0
      ;;
    parallel)
      # Skip to parallel section
      ;;
    *)
      echo "Unknown target: $1"
      echo "Usage: $0 [login|attendance|scores|users|bills|parallel]"
      exit 1
      ;;
  esac
fi

# ──────────────────────────────────────────────────────────────────
# SEQUENTIAL RUN (Baseline)
# ──────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════════"
echo "  PHASE 1: Sequential Baseline Run"
echo "════════════════════════════════════════════════════════════"

run_single "login"       "${SCRIPT_DIR}/login.js"
run_single "attendance"  "${SCRIPT_DIR}/attendance.js"
run_single "scores"      "${SCRIPT_DIR}/scores.js"
run_single "users"       "${SCRIPT_DIR}/users.js"
run_single "bills"       "${SCRIPT_DIR}/bills.js"

echo ""
echo "  ✓ Sequential baseline complete."
echo "  Reports: $(ls ${REPORT_DIR}/*.json | wc -l) files"

# ──────────────────────────────────────────────────────────────────
# PARALLEL RUN (All endpoints simultaneously)
# ──────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════════"
echo "  PHASE 2: Parallel Run (all endpoints)"
echo "════════════════════════════════════════════════════════════"

# Clean up previous parallel reports
rm -f "${REPORT_DIR}"/parallel_*.json

# Launch all 5 tests concurrently
PARALLEL_REPORT_DIR="${REPORT_DIR}"

$K6 run "${SCRIPT_DIR}/login.js" \
  --summary-export="${PARALLEL_REPORT_DIR}/parallel_login.json" \
  -e BASE_URL="$BASE_URL" &
PID_LOGIN=$!

$K6 run "${SCRIPT_DIR}/attendance.js" \
  --summary-export="${PARALLEL_REPORT_DIR}/parallel_attendance.json" \
  -e BASE_URL="$BASE_URL" &
PID_ATTENDANCE=$!

$K6 run "${SCRIPT_DIR}/scores.js" \
  --summary-export="${PARALLEL_REPORT_DIR}/parallel_scores.json" \
  -e BASE_URL="$BASE_URL" &
PID_SCORES=$!

$K6 run "${SCRIPT_DIR}/users.js" \
  --summary-export="${PARALLEL_REPORT_DIR}/parallel_users.json" \
  -e BASE_URL="$BASE_URL" &
PID_USERS=$!

$K6 run "${SCRIPT_DIR}/bills.js" \
  --summary-export="${PARALLEL_REPORT_DIR}/parallel_bills.json" \
  -e BASE_URL="$BASE_URL" &
PID_BILLS=$!

echo "  Parallel processes launched:"
echo "    login      (PID $PID_LOGIN)"
echo "    attendance (PID $PID_ATTENDANCE)"
echo "    scores     (PID $PID_SCORES)"
echo "    users      (PID $PID_USERS)"
echo "    bills      (PID $PID_BILLS)"

# Wait for all parallel jobs to finish
FAILED=0
for pid in "$PID_LOGIN" "$PID_ATTENDANCE" "$PID_SCORES" "$PID_USERS" "$PID_BILLS"; do
  wait "$pid" || ((FAILED++))
done

echo ""
if [[ $FAILED -eq 0 ]]; then
  echo "  ✓ All parallel tests completed successfully."
else
  echo "  ⚠  $FAILED parallel test(s) reported errors."
fi

# ──────────────────────────────────────────────────────────────────
# SUMMARY
# ──────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════════"
echo "  RESULTS SUMMARY"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "  Sequential reports:"
for f in "${REPORT_DIR}"/login.json "${REPORT_DIR}"/attendance.json \
         "${REPORT_DIR}"/scores.json "${REPORT_DIR}"/users.json \
         "${REPORT_DIR}"/bills.json; do
  if [[ -f "$f" ]]; then
    name=$(basename "$f" .json)
    # Extract key metrics: p50, p95, p99, req/s, error rate
    p50=$(jq -r '.metrics.request_duration.value.med // "N/A"' "$f" 2>/dev/null)
    p95=$(jq -r '.metrics.request_duration.value."p(95)" // "N/A"' "$f" 2>/dev/null)
    p99=$(jq -r '.metrics.request_duration.value."p(99)" // "N/A"' "$f" 2>/dev/null)
    rps=$(jq -r '.metrics.http_reqs.value.rate // "N/A"' "$f" 2>/dev/null)
    err=$(jq -r '.metrics.failure_rate.value.rate // "N/A"' "$f" 2>/dev/null)
    echo "    $name:  req/s=$rps  p50=${p50}ms  p95=${p95}ms  p99=${p99}ms  err=$err"
  fi
done

echo ""
echo "  Parallel reports:"
for f in "${REPORT_DIR}"/parallel_*.json; do
  if [[ -f "$f" ]]; then
    name=$(basename "$f" .json)
    p50=$(jq -r '.metrics.request_duration.value.med // "N/A"' "$f" 2>/dev/null)
    p95=$(jq -r '.metrics.request_duration.value."p(95)" // "N/A"' "$f" 2>/dev/null)
    p99=$(jq -r '.metrics.request_duration.value."p(99)" // "N/A"' "$f" 2>/dev/null)
    rps=$(jq -r '.metrics.http_reqs.value.rate // "N/A"' "$f" 2>/dev/null)
    err=$(jq -r '.metrics.failure_rate.value.rate // "N/A"' "$f" 2>/dev/null)
    printf "    %-25s req/s=%-8s p50=%-8s p95=%-8s p99=%-8s err=%s\n" "$name" "$rps" "${p50}ms" "${p95}ms" "${p99}ms" "$err"
  fi
done

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  Suite complete. Reports: ${REPORT_DIR}/"
echo "════════════════════════════════════════════════════════════"
