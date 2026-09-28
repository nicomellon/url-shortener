# Experiments

Experiments to run against this app, with the load tests and dashboard described in
the README. For each one: write down a prediction first, run the same load test
before and after, and compare the p50/p95/p99 and throughput on the dashboard.

## Baseline

What each experiment compares against. `make bench BENCH_WORKERS="4 8"`: reads
ramp from 2,000 to 16,000/s in 15s steps, plus 100 writes/s. 1M seeded URLs,
uniform keys, pool 5 + 5 per worker. Same machine as below (12-core Mac, Postgres
in Colima with 6 CPUs). Recorded after single-statement reads (2026-09-28).

| Workers | Highest step sustained | Server p99 there | Peak throughput | API µs / DB µs per read, at 4,000/s |
| --- | --- | --- | --- | --- |
| 4 | 6,000 req/s | 20 ms | 7,273 (p99 495 ms) | 273 / 44 |
| 8 | 8,000 req/s | 9 ms | 9,925 (p99 91 ms, the Mac at 95%) | 314 / 40 |

- **Python costs about 7× more CPU per read than Postgres.** Changes to the API
  process (ORM vs raw SQL, async, a cache) have the most room to show up.
- **8 workers reach the DDIA target of 10,000 reads/s, but only just, and with
  the whole Mac saturated** (1,135% of 1,200%: API ~6.8 cores, Postgres ~5, k6
  ~1.2), and k6 already dropping 43 requests/s. At that point CPU contention
  inflates everything's cost: Postgres went from 40 to 521 µs per read. So
  compare µs per request at steps *below* saturation.
- Past the ceiling nothing failed, but throughput fell and k6 dropped requests it
  couldn't send (4 workers: 6,955 req/s at 12,000 offered).
- Past the ceiling k6's p99 is about 8.2 s while the server's is under 0.5 s: the
  connections that don't fit in the accept queue have their SYNs retried after 1,
  2 and 4 s. The server's latency can't see this queue at all, only the client's
  can.

## To do

### Sync vs. async request handling

Today the routes are sync (`def`): FastAPI runs each one in a thread pool (40
threads by default), and SQLAlchemy/psycopg block that thread while waiting on
Postgres.

- **Change:** make the routes `async def`, and switch to SQLAlchemy's asyncio
  extension (`create_async_engine`, `AsyncSession`) with psycopg's async driver.
  Services and views become `async` too.
- **Trap to avoid:** `async def` routes that still call the *sync* driver block the
  event loop, so every request waits behind every database call. Measure it once
  deliberately to see how bad it is.
- **Questions:** Does throughput go up once the thread pool isn't the limit? What
  happens to tail latency? Where does the bottleneck move (CPU of the single Python
  process, the connection pool, Postgres)?
- **Remember:** each request still needs its own session. Coroutines interleave at
  every `await`, so sharing a session between requests breaks in async code too.

### ORM vs. raw SQL

Writes go through the SQLAlchemy ORM (`session.add`, identity map, unit-of-work
flush); reads already use a raw `text()` query in `views.py`.

- **Change:** rewrite `services.create_short_url` as a Core `insert()` or raw SQL,
  and compare the read path with an ORM `session.get()` version.
- **Questions:** How much CPU per request is the ORM? Does it matter at the
  database's saturation point, or only when Python is the bottleneck? What do we
  lose in readability and safety?
- **Tip:** compare at a fixed rate below saturation (CPU usage and p50) and at the
  breaking point (`ramp.js`).

### Another language for the hot path

A read costs about 300 µs of API CPU and 40 µs in Postgres (see Baseline). How much
of that is Python, and how much is our stack: FastAPI's routing and dependency
injection, the metrics middleware, the thread-pool hop for sync routes, SQLAlchemy?

- **First:** profile a worker under load (py-spy flame graph) to split those up.
  Some of the cost may be fixable without leaving Python.
- **Change:** a small Go service serving only `GET /{short_code}` (net/http and
  pgx) against the same Postgres, benchmarked with the same ramp.
- **Prediction:** 5–10× less API CPU per read, but on one Mac the ceiling rises only
  2–3× before Postgres and k6 saturate it.
- **Questions:** Is the gain worth a second codebase and toolchain? A faster
  language lowers the cost per request (a constant factor), while scaling out
  changes how capacity grows with machines (DDIA ch. 1).

### Shared cache (Redis) vs. local cache

The read cache (see Done) is per process. A shared cache like Redis trades a
network round trip per lookup for one warm copy shared by every worker and machine.
That copy survives deploys, and memory isn't duplicated.

- **Change:** a Redis-backed cache behind the same `get`/`put` interface, then an
  in-process cache in front of Redis (two tiers).
- **Questions:** Is a Redis hit cheaper than the Postgres primary-key lookup it
  replaces, given the table already fits in Postgres' memory? How much does the hit
  rate improve with one cache instead of one per worker? What happens right after
  a deploy (cold caches)? What does the API do when Redis is down: fall back to
  Postgres, or fail? Is it one more single point of failure?

### Load shedding

Under overload the API accepts every request and queues it, so throughput *drops*
(1 worker: 1,528 req/s at 3,000 offered, 1,119 at 8,000) and everyone waits
seconds. Try capping concurrency per worker (uvicorn `limit_concurrency`) so excess
requests fail fast with 503, and compare goodput and p99.

## Done

### Read cache

Short URLs never change once created and are never deleted, so a cache of code →
URL never needs invalidating, and each worker can keep its own.

**Change:** `adapters/cache.py`, an LRU cache per worker (`READ_CACHE_SIZE`,
default 100,000 URLs, about 30 MB). `views.get_url` checks it before querying, and
caches only URLs it found: a 404 isn't cached, since the code may be created a
moment later.

**Why in-process rather than Redis:** Postgres isn't the bottleneck (40 µs of CPU
per read against 314 µs in the API), and the table is already in its memory. A
Redis hit still costs a network round trip and client work, while a local hit
costs about 1 µs. Redis is a follow-up experiment (see To do).

**Predictions:**
- **Hit rate:** `lib.js` picks index N·u^SKEW, so the k most popular URLs get
  (k/N)^(1/SKEW) of the reads. With 100,000 entries per worker and 1M URLs, the
  best any cache can do is 10% with `SKEW=1` and 46% with `SKEW=3`. LRU does a
  bit worse, and each of the 8 workers warms its own cache.
- **Cost:** Postgres µs per read falls with the hit rate. API µs falls much less,
  because a hit still does the HTTP, routing and middleware work.
- **Ceiling:** with `SKEW=3` it rises modestly, as CPU Postgres no longer uses goes
  to the API. With `SKEW=1` there's little change.
- Without the cache, skew alone barely matters: the whole table is in memory.

**Setup:** as the Baseline, 8 workers, with the cache off and on, for uniform
(`SKEW=1`) and hot (`SKEW=3`) keys. All four runs were back to back, so they're
compared with each other rather than with the Baseline (see the last finding).
Hit rates are for each step; they rise through the run as caches warm.

| 8 workers | Cache off, `SKEW=1` | Cache on, `SKEW=1` | Cache off, `SKEW=3` | Cache on, `SKEW=3` |
| --- | --- | --- | --- | --- |
| Hit rate at 4,000 → 16,000 req/s | | 2% → 10% | | 13% → 32% |
| API / DB µs per read at 6,000 req/s | 381 / 60 | 360 / 53 | 389 / 62 | 357 / 45 |
| At 8,000 req/s: server p99, Postgres CPU, whole Mac | 21 ms, 265%, 845% | 12 ms, 269%, 726% | 63 ms, 271%, 938% | **3 ms, 35%, 495%** |
| At 10,000 req/s: throughput, server p99 | 8,855, 392 ms | 8,612, 418 ms | 9,451, 401 ms | **9,925, 116 ms** |
| Peak throughput | 9,346 | 9,135 | 9,451 | **10,669** |

**Findings:**
- **Uniform keys: no gain.** A 100,000-entry cache over 1M equally popular URLs
  can't hit more than 10%, and it got there only at the end of the run.
- **Hot keys: a modest hit rate, a large effect near the limit.** At 8,000 req/s
  with the cache off, Postgres CPU jumped from 37% (at 6,000) to 271%, and the
  whole Mac to 938%. Everything competed for CPU and got slower together. A 21% hit
  rate kept the system below that knee: Postgres at 35%, p99 at 3 ms instead of
  63 ms. Near saturation, response time grows much faster than load (DDIA ch. 1's
  queueing), so taking a small share of the load off has an outsized effect.
  The peak rose 13% (9,451 → 10,669).
- **Hit rates were below the prediction** (32% at the end, against at most 46%),
  because the caches never warmed up. Each worker only sees an eighth of the
  reads, so in a 3-minute run it saw about 175,000 reads, barely more than the
  cache holds. This is the per-process cache's weakness: 8 cold copies to fill,
  and they're emptied again on every deploy. A shared cache fills once (see
  "Shared cache (Redis) vs. local cache").
- **API µs per read barely moved** (357 vs 389 at 6,000 with hot keys), as
  predicted: a hit still does the HTTP, routing and middleware work. The
  difference is within the noise between runs.
- **Runs vary by 10–20%.** Today's cache-off uniform run peaked at 9,346 req/s,
  against 9,925 for the Baseline earlier in the day, with the same code and
  settings. The Mac's background load changes, so compare runs made back to back.

### One round trip per read

Every read ran `BEGIN`, `SELECT`, `ROLLBACK`: the ORM session opened a transaction
and closing it rolled back.

**Prediction:** one statement instead of three should cut Postgres CPU per read by
a lot and API CPU somewhat, and move the 8-worker ceiling, since the Mac was
saturated there.

**Change:** views take the engine and run their query on an autocommit connection
(`engine.execution_options(isolation_level="AUTOCOMMIT")`, which shares the pool),
so a read is a single `SELECT`, with no ORM session. Writes keep a transactional
session.

**Setup:** as for scaling out below (same ramp, 1 and 8 workers).

| | Before | After |
| --- | --- | --- |
| One read, measured in a loop | 320 µs | 145 µs |
| Postgres at ~5,800 reads/s | 5,790 rollbacks/s | 0 rollbacks/s (every `SELECT` counts as a commit) |
| 1 worker: highest step sustained | 2,000 req/s | 3,000 req/s |
| 1 worker at 2,000 req/s: API CPU / Postgres CPU | 0.73 cores / 19% | 0.45 cores / 7% |
| 8 workers: highest step sustained | 6,000 req/s (p99 52 ms) | 8,000 req/s (p99 40 ms), the top of the ramp |
| 8 workers at 5,000 req/s: API CPU / Postgres CPU | 3.6 cores / 93% | 1.7 cores / 21% |
| 8 workers at 6,000 req/s: whole Mac | 1,128% (of 1,200%) | 342% |

**Findings:**
- Better than predicted: Postgres CPU per read fell by about 4×, and API CPU by
  about 2×, because skipping the session also skips the ORM's bookkeeping. The
  8-worker ceiling is now above 8,000 req/s, and the Mac has headroom left: the next
  ramp should go to 10,000+.
- One worker now tops out at about 3,000 req/s. Past that, k6 hit `dial: i/o
  timeout` (up to 9.5% of requests): the queue of connections waiting to be
  accepted overflowed (macOS `kern.ipc.somaxconn` is 128).
- A single `SELECT` sees one consistent snapshot on its own, so this is safe. A
  view that runs several queries which must agree needs a transaction again, or it
  risks read skew (DDIA ch. 7).
- **Deadlock found on the way:** the first version checked out the read connection
  in a FastAPI dependency. FastAPI runs a dependency's setup and the route on
  separate thread-pool threads, so under load (about 3,000 req/s) every connection
  was held by a request waiting for a thread, and every thread by a request
  waiting for a connection. The API froze until the pool timed out (1,280
  `QueuePool` timeouts, 15% failed requests), and it didn't shut down. Fixed by
  opening the connection inside the view, around the query only. Rule: take
  connections late, release them early.

### Scaling out with worker processes (DDIA ch. 1)

**Prediction:** one Python process is CPU-bound (the GIL), so throughput should
scale with workers until something else saturates.

**Setup:** `ramp.js`, reads stepping from 1,000 to 8,000/s (15s steps), 100
writes/s, 1M seeded URLs, uniform keys. k6 on the Mac; Postgres in Colima (6 CPUs,
8 GiB), reached through the VM's IP; `DB_POOL_SIZE=5 DB_MAX_OVERFLOW=5` per
worker. Mac: 12 cores. 0 failed requests across all runs (2.2M requests).

| Workers | Highest step sustained (p99 < 100 ms) | Peak throughput | API CPU there | Server p99 there |
| --- | --- | --- | --- | --- |
| 1 | 2,000 req/s | 2,007 | 0.7 cores | 8 ms |
| 2 | 3,000 req/s | 3,799 (p99 301 ms) | 1.3 cores | 8 ms |
| 4 | 4,000 req/s | 4,705 (p99 360 ms) | 2.3 cores | 20 ms |
| 8 | 6,000 req/s | 5,969 | 6.8 cores | 52 ms |

**Findings:**
- Confirmed: a single worker saturates at about 1.3–1.6 cores (not 1.0: psycopg and
  uvloop do some work outside the GIL). Postgres was at 15–20% CPU meanwhile.
- Scaling is sublinear: 1 → 2 workers nearly doubles capacity, then each doubling
  gains about 30%.
- At 8 workers the **whole Mac** is saturated (about 94% of 12 cores: API ~7,
  Postgres VM ~3.6, k6 ~1). More workers won't help on one machine; the DDIA target
  of 10,000 reads/s needs cheaper requests or more machines.
- Past saturation, throughput falls as offered load rises (see Load shedding).
- Side finding: Colima's default SSH port forwarder took Postgres round trips from
  103 µs to 248 µs, and crashed at a few thousand queries/s, taking the Docker
  socket with it. A proxy in the data path became both a bottleneck and a single
  point of failure.

### Shared unit of work under concurrency

A single message bus and unit of work shared across FastAPI's thread pool made
concurrent writes overwrite each other's session: 17 failed writes at 3,000
reads/s. Fixed by removing the bus and unit of work and using one session per
request. Regression test: `tests/e2e/test_concurrency.py`.
