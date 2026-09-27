// Shared by the load test scripts. Configure them with -e NAME=value.
import http from "k6/http";
import { check } from "k6";

export const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
// How many URLs `url-shortener-admin seed-urls` inserted
export const SEED_COUNT = parseInt(__ENV.SEED_COUNT || "1000000");
// 1 = every seeded URL equally likely. Higher = a few "hot" URLs get most reads.
export const SKEW = parseFloat(__ENV.SKEW || "1");

// Must match SEED_CODE_ALPHABET and seed_short_code in entrypoints/admin.py
const ALPHABET =
  "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ";
const CODE_LENGTH = 7;

export function seedShortCode(index) {
  let code = "";
  for (let i = 0; i < CODE_LENGTH; i++) {
    code = ALPHABET[index % ALPHABET.length] + code;
    index = Math.floor(index / ALPHABET.length);
  }
  return code;
}

function randomSeedIndex() {
  // Raising a uniform random number to a power > 1 piles values up near 0,
  // so low indices become hot keys
  return Math.floor(SEED_COUNT * Math.pow(Math.random(), SKEW));
}

export function readShortURL() {
  const res = http.get(`${BASE_URL}/${seedShortCode(randomSeedIndex())}`, {
    redirects: 0, // measure our redirect, not a trip to example.com
    tags: { name: "GET /{short_code}" },
  });
  check(res, { "redirected (302)": (r) => r.status === 302 });
}

export function createShortURL() {
  const url = `https://example.com/load-test/${Date.now()}-${Math.random()}`;
  const res = http.post(`${BASE_URL}/urls`, JSON.stringify({ url }), {
    headers: { "Content-Type": "application/json" },
    tags: { name: "POST /urls" },
  });
  check(res, { "created (201)": (r) => r.status === 201 });
}

// Percentiles, not averages: the mean hides the slow requests users notice
export const summaryTrendStats = [
  "avg",
  "med",
  "p(90)",
  "p(95)",
  "p(99)",
  "p(99.9)",
  "max",
];
