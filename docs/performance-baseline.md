# SchoolCare v2 — Performance Baseline

## 1. Test Environment

| Attribute          | Value                              |
|--------------------|------------------------------------|
| **Application**    | SchoolCare v2 (Go + Gin backend)  |
| **API Base URL**   | `http://localhost:8080/api/v2`     |
| **Database**       | PostgreSQL (via GORM)              |
| **Cache**          | Redis                              |
| **Load Tester**    | k6 v0.50+                          |
| **Host**           | TBD (development/staging/production) |
| **Date**           | TBD                                |
| **k6 VUs**         | 10                                  |
| **Test Duration**  | 30s per endpoint                    |
| **Think Time**     | 1s between requests                 |

### 1.1 Hardware (Reference)

| Component | Specification |
|-----------|---------------|
| CPU       | TBD           |
| RAM       | TBD           |
| Disk      | TBD           |
| Network   | TBD           |

---

## 2. Endpoint Definitions

| # | Script      | Method | Path                                    | Payload / Query                                    |
|---|-------------|--------|-----------------------------------------|----------------------------------------------------|
| 1 | `login.js`  | POST   | `/api/v2/auth/login`                    | `{ "identifier": "admin@school.com", "password": "password" }` |
| 2 | `attendance.js` | GET | `/api/v2/academic/attendance`           | `?student_id=1&start_date=2026-01-01&end_date=2026-06-30` |
| 3 | `scores.js`  | POST  | `/api/v2/academic/scores`               | `{ "student_id": 1, "subject_id": 1, "score": 85, "max_score": 100 }` |
| 4 | `users.js`   | GET   | `/api/v2/users/list`                    | `?page=1&per_page=20` (also tests `?role=student`) |
| 5 | `bills.js`   | GET   | `/api/v2/bills`                         | `?student_id=1` (also tests with `start_date`/`end_date`) |

### 2.1 Authentication

Endpoints 2–5 require a Bearer token obtained from the login endpoint. The `setup()` function in each script
authenticates once and shares the token across all VU iterations via the k6 `data` parameter.

**Auth header format:**
```
Authorization: Bearer <token>
x-school-id: 1
```

### 2.2 k6 Options (applied to all scripts)

| Option     | Value   |
|------------|---------|
| `vus`      | 10      |
| `duration` | 30s     |

### 2.3 Custom Metrics

| Metric             | Type   | Description                        |
|--------------------|--------|------------------------------------|
| `failure_rate`     | Rate   | Proportion of failed requests      |
| `request_duration` | Trend  | Request latency distribution (ms)  |

### 2.4 Thresholds (Performance Budget)

| Threshold                    | Target           | Description                        |
|------------------------------|------------------|------------------------------------|
| `failure_rate < 0.01`        | < 1% errors      | Error rate must stay under 1%      |
| `request_duration p(95) < 500` | < 500ms p95   | 95th percentile latency under 500ms |

---

## 3. Baseline Results Template

Run `./scripts/loadtest/run.sh` to generate results. Fill in the table below.

### 3.1 Sequential Run (Isolated Endpoints)

| Endpoint    | Req/s    | p50 (ms) | p95 (ms) | p99 (ms) | Error Rate |
|-------------|----------|----------|----------|----------|------------|
| Login       | TBD      | TBD      | TBD      | TBD      | TBD        |
| Attendance  | TBD      | TBD      | TBD      | TBD      | TBD        |
| Scores      | TBD      | TBD      | TBD      | TBD      | TBD        |
| Users       | TBD      | TBD      | TBD      | TBD      | TBD        |
| Bills       | TBD      | TBD      | TBD      | TBD      | TBD        |

### 3.2 Parallel Run (Concurrent Load)

| Endpoint       | Req/s    | p50 (ms) | p95 (ms) | p99 (ms) | Error Rate |
|----------------|----------|----------|----------|----------|------------|
| Login          | TBD      | TBD      | TBD      | TBD      | TBD        |
| Attendance     | TBD      | TBD      | TBD      | TBD      | TBD        |
| Scores         | TBD      | TBD      | TBD      | TBD      | TBD        |
| Users          | TBD      | TBD      | TBD      | TBD      | TBD        |
| Bills          | TBD      | TBD      | TBD      | TBD      | TBD        |

---

## 4. How to Run Tests

### 4.1 Prerequisites

- k6 installed at `/home/playbit/go/bin/k6` (or update `K6_BIN` env var)
- Backend running on `http://localhost:8080` (or set `BASE_URL` env var)
- `jq` installed for summary parsing (`sudo apt install jq`)

### 4.2 Commands

```bash
# Full test suite (sequential + parallel)
./scripts/loadtest/run.sh

# Test a single endpoint
./scripts/loadtest/run.sh login
./scripts/loadtest/run.sh attendance

# Parallel-only run
./scripts/loadtest/run.sh parallel

# Custom base URL
BASE_URL=http://staging.example.com ./scripts/loadtest/run.sh

# Custom k6 binary path
K6_BIN=./k6 ./scripts/loadtest/run.sh
```

### 4.3 Output

All results are exported as JSON reports to `scripts/loadtest/reports/`:

| File                        | Description                        |
|-----------------------------|------------------------------------|
| `login.json`                | Sequential login results           |
| `attendance.json`           | Sequential attendance results      |
| `scores.json`               | Sequential scores results          |
| `users.json`                | Sequential users results           |
| `bills.json`                | Sequential bills results           |
| `parallel_login.json`       | Parallel login results             |
| `parallel_attendance.json`  | Parallel attendance results        |
| `parallel_scores.json`      | Parallel scores results            |
| `parallel_users.json`       | Parallel users results             |
| `parallel_bills.json`       | Parallel bills results             |

---

## 5. Performance Budget Thresholds

| Threshold                   | Target | Violation Action                                  |
|-----------------------------|--------|---------------------------------------------------|
| Error rate (p95)            | < 1%   | Investigate backend errors, DB connection pool    |
| Latency p95                 | < 500ms | Profile slow endpoints, check DB query plans     |
| Latency p99                 | < 1000ms | Check for GC pauses, connection bottlenecks     |
| Parallel throughput drop    | < 30%  | Investigate contention, connection pool limits    |

---

## 6. Interpreting Results

### 6.1 Key Metrics

- **Req/s (Requests per second)**: Throughput. Higher is better. Compare sequential vs parallel to understand
  how endpoints contend for resources.

- **p50 (Median latency)**: Typical user experience. Values under 200ms are good.

- **p95 (95th percentile latency)**: Represents the experience for the slowest 5% of requests.
  Should stay under 500ms. Spikes here often indicate GC pauses or DB connection contention.

- **p99 (99th percentile latency)**: Tail latency. Should stay under 1000ms. Values above this
  indicate serious bottlenecks.

- **Error rate**: Should remain below 1%. Errors in load tests often indicate rate limiting,
  connection pool exhaustion, or authentication token issues under load.

### 6.2 Sequential vs Parallel

| Metric              | Sequential (Isolated) | Parallel (Contention) |
|---------------------|-----------------------|-----------------------|
| Throughput (req/s)  | Per-endpoint baseline | Total system capacity |
| Latency             | No contention         | Realistic contention  |
| Error rate          | Baseline errors       | Stress-induced errors |

A significant throughput drop or latency increase from sequential to parallel suggests the backend
has resource contention (DB connections, goroutine pool limits, etc.).

### 6.3 Common Regressions

| Symptom                          | Likely Cause                                  |
|----------------------------------|-----------------------------------------------|
| p95 latency spikes on GET endpoints | DB query missing index, N+1 queries         |
| High error rate on POST endpoints | Validation errors under load, rate limiting   |
| Throughplate drop in parallel     | PostgreSQL connection pool exhaustion         |
| Login endpoint degradation        | bcrypt cost too high, Redis contention        |
| All endpoints degrade together    | CPU saturation, memory pressure, GC thrashing |

---

## 7. Continuous Performance Monitoring

Whenever a significant change is made to the backend (new middleware, DB migration,
dependency upgrade), re-run the baseline and compare:

```bash
# Archive current baseline
cp -r scripts/loadtest/reports scripts/loadtest/reports_$(date +%Y%m%d)

# Run new tests
./scripts/loadtest/run.sh

# Compare
diff <(jq '.metrics.request_duration.value."p(95)"' scripts/loadtest/reports/*.json | sort) \
     <(jq '.metrics.request_duration.value."p(95)"' scripts/loadtest/reports_*/login.json | sort)
```

Automate this comparison in CI to fail builds that degrade p95 latency by more than 20%.
