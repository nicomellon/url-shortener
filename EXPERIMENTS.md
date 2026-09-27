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

## Done

- **Shared unit of work under concurrency (DDIA ch. 1).** A single message bus and
  unit of work shared across FastAPI's thread pool made concurrent writes overwrite
  each other's session: 17 failed writes at 3,000 reads/s. Fixed by removing the bus
  and unit of work and using one session per request. Regression test:
  `tests/e2e/test_concurrency.py`.
