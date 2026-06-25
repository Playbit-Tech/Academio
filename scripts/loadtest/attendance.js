// k6 load test: GET /api/v2/academic/attendance
// Uses native ES modules (k6 v0.50+)
// Authenticated: requires Bearer token from login

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

// ── Student IDs to iterate over ─────────────────────────────────
const STUDENT_IDS = [1, 2, 3, 4, 5];
const START_DATE = '2026-01-01';
const END_DATE = '2026-06-30';

// ── Setup: authenticate once and share token across VUs ──────────
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

  // Pick a student ID based on current VU and iteration
  const studentId = STUDENT_IDS[__VU % STUDENT_IDS.length];

  const params = {
    ...headers,
    tags: { student_id: String(studentId) },
  };

  const res = http.get(
    `${BASE_URL}/api/v2/academic/attendance?student_id=${studentId}&start_date=${START_DATE}&end_date=${END_DATE}`,
    params,
  );

  // Record metrics
  const isSuccess = res.status === 200;
  failureRate.add(!isSuccess);
  requestDuration.add(res.timings.duration);

  // Checks
  check(res, {
    'attendance status is 200': (r) => r.status === 200,
    'attendance response is valid JSON': (r) => {
      try {
        JSON.parse(r.body);
        return true;
      } catch {
        return false;
      }
    },
    'attendance response has success flag': (r) => {
      try {
        return JSON.parse(r.body).success === true;
      } catch {
        return false;
      }
    },
    'attendance response time < 500ms': (r) => r.timings.duration < 500,
  });

  // Simulate real user think time
  sleep(1);
}
