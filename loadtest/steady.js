// Constant load at a fixed read/write rate, like steady production traffic.
//
// Uses an open model (constant-arrival-rate): requests start on schedule whether
// or not earlier ones have finished, like independent users would. If the API
// slows down, requests queue up and the latency you see includes that queueing.
// A closed model (each user waits for a response before the next request) would
// quietly send less load instead, and hide the problem.
//
// Target (DDIA ch. 1 exercise): 10,000 reads/s and 100 writes/s over 10M URLs.
// The defaults are scaled down by 10x; raise them with -e READ_RATE=... etc.
import { createShortURL, readShortURL, summaryTrendStats } from "./lib.js";

const READ_RATE = parseInt(__ENV.READ_RATE || "1000");
const WRITE_RATE = parseInt(__ENV.WRITE_RATE || "10");
const DURATION = __ENV.DURATION || "5m";

function constantRate(exec, rate) {
  return {
    executor: "constant-arrival-rate",
    exec,
    rate,
    timeUnit: "1s",
    duration: DURATION,
    // VUs are k6's concurrent workers: enough to keep up the rate while each
    // waits on a slow response. If k6 runs out, it reports dropped_iterations.
    preAllocatedVUs: Math.max(10, Math.ceil(rate / 10)),
    maxVUs: Math.max(100, rate),
  };
}

export const options = {
  scenarios: {
    reads: constantRate("reads", READ_RATE),
    writes: constantRate("writes", WRITE_RATE),
  },
  summaryTrendStats,
};

export function reads() {
  readShortURL();
}

export function writes() {
  createShortURL();
}
