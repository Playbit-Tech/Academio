// k6 load test: GET /api/v2/bills
// Uses native ES modules (k6 v0.50+)
// Authenticated: requires Bearer token from login
// Tests both basic and date-filtered queries

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';
import { getAuthToken, authHeaders } from './login.js';

// ── Custom Metrics ──────────────────────────────────────────────
const failureRate = new Rate('failure_rate');
const requestDuration = new Trend('request_duration');

// ── Options ─────────────────────────────────────────────────────
export const options = {
  vus: 10,
  duration: '30s',
  thresholds: {
    failure_rate: ['rate<0.01'],
    request_duration: ['p(95)<500'],
  },
};

// ── Base URL ────────────────────────────────────────────────────
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8080';

// ── Test data ───────────────────────────────────────────────────
const STUDENT_IDS = [1, 2, 3, 4, 5];

// ── Setup: authenticate once ────────────────────────────────────
export function setup() {
  const { token } = getAuthToken();
  if (!token) {
    throw new Error('Failed to obtain auth token in setup()');
  }
  return { token };
}

// ── Default function ─────────────────────────────────────────────
export default function (data) {
  const headers = authHeaders(data.token);
  const studentId = STUDENT_IDS[__VU % STUDENT_IDS.length];

  // Alternate between basic query and date-range query
  let url;
  if (__ITER % 2 === 0) {
    // Basic query by student
    url = `${BASE_URL}/api/v2/bills?student_id=${studentId}`;
  } else {
    // Date-range filtered query
    url = `${BASE_URL}/api/v2/bills?student_id=${studentId}&start_date=2026-01-01&end_date=2026-06-30`;
  }

  const params = {
    ...headers,
    tags: { student_id: String(studentId), variant: __ITER % 2 === 0 ? 'basic' : 'date_range' },
  };

  const res = http.get(url, params);

  // Record metrics
  const isSuccess = res.status === 200;
  failureRate.add(!isSuccess);
  requestDuration.add(res.timings.duration);

  // Checks
  check(res, {
    'bills status is 200': (r) => r.status === 200,
    'bills response is valid JSON': (r) => {
      try {
        JSON.parse(r.body);
        return true;
      } catch {
        return false;
      }
    },
    'bills response has success flag': (r) => {
      try {
        return JSON.parse(r.body).success === true;
      } catch {
        return false;
      }
    },
    'bills response data is an array or object': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.data !== undefined;
      } catch {
        return false;
      }
    },
    'bills response time < 500ms': (r) => r.timings.duration < 500,
  });

  // Simulate real user think time
  sleep(1);
}
