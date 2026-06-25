// k6 load test: GET /api/v2/users/list
// Uses native ES modules (k6 v0.50+)
// Authenticated: requires Bearer token from login
// Tests both default listing and role-filtered variants

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

// ── Pagination variants ─────────────────────────────────────────
const PAGES = [1, 2, 3];
const PER_PAGE = 20;
const ROLE_FILTERS = ['', 'student', 'teacher', 'parent', 'admin'];

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

  // Alternate between plain list and role-filtered list
  const useRoleFilter = __ITER % 2 === 0;
  let url;

  if (useRoleFilter) {
    const role = ROLE_FILTERS[__VU % ROLE_FILTERS.length];
    if (role) {
      url = `${BASE_URL}/api/v2/users/list/${role}?page=1&per_page=${PER_PAGE}`;
    } else {
      url = `${BASE_URL}/api/v2/users/list?page=1&per_page=${PER_PAGE}`;
    }
  } else {
    const page = PAGES[__ITER % PAGES.length];
    url = `${BASE_URL}/api/v2/users/list?page=${page}&per_page=${PER_PAGE}`;
  }

  const params = {
    ...headers,
    tags: { vu: String(__VU), iter: String(__ITER) },
  };

  const res = http.get(url, params);

  // Record metrics
  const isSuccess = res.status === 200;
  failureRate.add(!isSuccess);
  requestDuration.add(res.timings.duration);

  // Checks
  check(res, {
    'users status is 200': (r) => r.status === 200,
    'users response is valid JSON': (r) => {
      try {
        JSON.parse(r.body);
        return true;
      } catch {
        return false;
      }
    },
    'users response has success flag': (r) => {
      try {
        return JSON.parse(r.body).success === true;
      } catch {
        return false;
      }
    },
    'users response has pagination meta': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.meta && body.meta.pagination && body.meta.pagination.page >= 1;
      } catch {
        return false;
      }
    },
    'users response time < 500ms': (r) => r.timings.duration < 500,
  });

  // Simulate real user think time
  sleep(1);
}
