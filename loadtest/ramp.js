// Increases the read rate step by step to find how much the API can take: watch
// for the point where latency percentiles shoot up, or requests start failing.
// Writes stay at a constant background rate.
import { createShortURL, readShortURL, summaryTrendStats } from "./lib.js";

const MAX_READ_RATE = parseInt(__ENV.MAX_READ_RATE || "5000");
const WRITE_RATE = parseInt(__ENV.WRITE_RATE || "10");
const STEPS = parseInt(__ENV.STEPS || "10");
const STEP_SECONDS = parseInt(__ENV.STEP_SECONDS || "60");
const RAMP_SECONDS = 10;

// Ramp up quickly to each step, then hold it, so each rate is measured on its own
const stages = [];
for (let step = 1; step <= STEPS; step++) {
  const target = Math.round((MAX_READ_RATE * step) / STEPS);
  stages.push(
    { target, duration: `${RAMP_SECONDS}s` },
    { target, duration: `${STEP_SECONDS}s` },
  );
}

export const options = {
  scenarios: {
    reads: {
      executor: "ramping-arrival-rate",
      exec: "reads",
      startRate: 0,
      timeUnit: "1s",
      stages,
      preAllocatedVUs: 50,
      maxVUs: Math.max(200, MAX_READ_RATE),
    },
    writes: {
      executor: "constant-arrival-rate",
      exec: "writes",
      rate: WRITE_RATE,
      timeUnit: "1s",
      duration: `${STEPS * (RAMP_SECONDS + STEP_SECONDS)}s`,
      preAllocatedVUs: 10,
      maxVUs: 100,
    },
  },
  summaryTrendStats,
};

export function reads() {
  readShortURL();
}

export function writes() {
  createShortURL();
}
