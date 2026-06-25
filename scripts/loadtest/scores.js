// k6 load test: POST /api/v2/academic/scores
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

// ── Test data pools ─────────────────────────────────────────────
const STUDENT_IDS = [1, 2, 3, 4, 5];
const SUBJECT_IDS = [1, 2, 3, 4, 5, 6, 7, 8];

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

  // Cycle through student and subject IDs
  const studentId = STUDENT_IDS[__VU % STUDENT_IDS.length];
  const subjectId = SUBJECT_IDS[__ITER % SUBJECT_IDS.length];

  const payload = JSON.stringify({
    student_id: studentId,
    subject_id: subjectId,
    score: Math.floor(Math.random() * 41) + 60, // 60-100
    max_score: 100,
  });

  const params = {
    ...headers,
    tags: { student_id: String(studentId), subject_id: String(subjectId) },
  };

  const res = http.post(
    `${BASE_URL}/api/v2/academic/scores`,
    payload,
    params,
  );

  // Record metrics
  const isSuccess = res.status === 200 || res.status === 201;
  failureRate.add(!isSuccess);
  requestDuration.add(res.timings.duration);

  // Checks
  check(res, {
    'scores status is 200 or 201': (r) => r.status === 200 || r.status === 201,
    'scores response is valid JSON': (r) => {
      try {
        JSON.parse(r.body);
        return true;
      } catch {
        return false;
      }
    },
    'scores response has success flag': (r) => {
      try {
        return JSON.parse(r.body).success === true;
      } catch {
        return false;
      }
    },
    'scores response time < 500ms': (r) => r.timings.duration < 500,
  });

  // Simulate real user think time
  sleep(1);
}
