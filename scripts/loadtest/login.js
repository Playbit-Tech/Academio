// k6 load test: POST /api/v2/auth/login
// Uses native ES modules (k6 v0.50+)
// Provides auth token used by all other test scripts

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// ── Custom Metrics ──────────────────────────────────────────────
const failureRate = new Rate('failure_rate');
const requestDuration = new Trend('request_duration');

// ── Options ─────────────────────────────────────────────────────
export const options = {
  vus: 10,
  duration: '30s',
  thresholds: {
    failure_rate: ['rate<0.01'], // error rate < 1%
    request_duration: ['p(95)<500'], // p95 < 500ms
  },
};

// ── Base URL ────────────────────────────────────────────────────
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8080';

// ── Default function (test login endpoint) ───────────────────────
export default function () {
  const payload = JSON.stringify({
    identifier: 'admin@school.com',
    password: 'password',
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
      'x-school-id': '1',
    },
  };

  const res = http.post(`${BASE_URL}/api/v2/auth/login`, payload, params);

  // Record metrics
  const isSuccess = res.status === 200;
  failureRate.add(!isSuccess);
  requestDuration.add(res.timings.duration);

  // Checks
  check(res, {
    'login status is 200': (r) => r.status === 200,
    'login response has success flag': (r) => {
      try {
        return JSON.parse(r.body).success === true;
      } catch {
        return false;
      }
    },
    'login response contains authorization token': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.data && body.data.authorization && typeof body.data.authorization.token === 'string';
      } catch {
        return false;
      }
    },
    'login response contains user data': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.data && body.data.user && body.data.user.id > 0;
      } catch {
        return false;
      }
    },
    'login response time < 500ms': (r) => r.timings.duration < 500,
  });

  // Simulate real user behavior: think time between requests
  sleep(1);
}

// ── Helpers (exported for reuse by other scripts) ────────────────

/**
 * Performs a login and returns the Bearer token string.
 * Used by setup() in authenticated test scripts.
 *
 * @returns {{ token: string, refreshToken: string }}
 */
export function getAuthToken() {
  const payload = JSON.stringify({
    identifier: 'admin@school.com',
    password: 'password',
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
      'x-school-id': '1',
    },
  };

  const res = http.post(`${BASE_URL}/api/v2/auth/login`, payload, params);

  if (res.status !== 200) {
    console.error('Login failed in setup():', res.status, res.body);
    return { token: '', refreshToken: '' };
  }

  const body = JSON.parse(res.body);
  return {
    token: body.data.authorization.token,
    refreshToken: body.data.authorization.refresh_token || '',
  };
}

/**
 * Returns the standard auth headers object for authenticated requests.
 * @param {string} token - Bearer token
 * @returns {object} Headers object
 */
export function authHeaders(token) {
  return {
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      'x-school-id': '1',
    },
  };
}
