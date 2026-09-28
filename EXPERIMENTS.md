# Experiments

Experiments to run against this app, with the load tests and dashboard described in
the README. For each one: write down a prediction first, run the same load test
before and after, and compare the p50/p95/p99 and throughput on the dashboard.

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

### Read cache

Short URLs never change once created, so a cache of code → URL never needs
invalidating. Try an in-process LRU cache first, and compare hit rates with
`SKEW=1` (uniform) and `SKEW=3` (hot keys).

### Load shedding

Under overload the API accepts every request and queues it, so throughput *drops*
(1 worker: 1,528 req/s at 3,000 offered, 1,119 at 8,000) and everyone waits
seconds. Try capping concurrency per worker (uvicorn `limit_concurrency`) so excess
requests fail fast with 503, and compare goodput and p99.

## Done

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
