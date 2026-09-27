# url-shortener

A URL shortener, built as a playground for the ideas in *Designing Data-Intensive
Applications* (Martin Kleppmann). It uses FastAPI, SQLAlchemy 2 and Postgres, a
layered architecture loosely based on [Cosmic Python](https://www.cosmicpython.com/)
(domain, service layer, adapters, entrypoints), and the
[twelve-factor app](https://12factor.net/) guidelines.

| Endpoint | Description |
| --- | --- |
| `POST /urls` | Body `{"url": "https://..."}`. Returns `201` with `short_code`, `short_url` and `url`. |
| `GET /{short_code}` | Redirects (`302`) to the original URL, or `404` if the code is unknown. |

For the architecture and conventions, see [AGENTS.md](AGENTS.md). For experiments
still to run, see [EXPERIMENTS.md](EXPERIMENTS.md).

## Getting started

Prerequisites: [uv](https://docs.astral.sh/uv/) and Docker.

1. **Install dependencies:**
   ```sh
   uv sync
   ```
2. **Create your local config:**
   ```sh
   cp .env.example .env
   ```
   If port 5432 is already in use on your machine, set `DB_PORT` (e.g. `55432`) in
   `.env` and change the port in `DATABASE_URL` to match.
3. **Start Postgres and create the tables:**
   ```sh
   docker compose up -d db
   uv run url-shortener-admin init-db
   ```
4. **Check that everything passes:**
   ```sh
   uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run lint-imports && uv run pytest
   ```
5. **Run the API** and open http://localhost:8000/docs to try the endpoints:
   ```sh
   uv run fastapi dev src/url_shortener/entrypoints/fastapi_app.py --port 8000
   ```

## Everyday commands

| Task | Command |
| --- | --- |
| Run the API with auto-reload | `uv run fastapi dev src/url_shortener/entrypoints/fastapi_app.py` |
| Run the API as in production | `uv run url-shortener-api` |
| Run tests | `uv run pytest` |
| Format / lint | `uv run ruff format .` / `uv run ruff check --fix .` |
| Type check | `uv run mypy` |
| Check architecture rules | `uv run lint-imports` |
| Add a dependency | `uv add <package>` (dev only: `uv add --group dev <package>`) |
| Run an admin task | `uv run url-shortener-admin <task>` |
| Run the whole stack in Docker | `docker compose up --build` |

## Layout

```
src/url_shortener/
├── domain/              # Pure business logic: the ShortURL model, code generation
├── service_layer/       # Use cases that change state (services.py)
├── adapters/            # Tables, ORM mappings, session factory
├── views.py             # Read-only queries
├── entrypoints/         # FastAPI app and routes, /metrics, admin CLI
└── config.py            # Settings from environment variables, logging setup
tests/
├── unit/                # No I/O
├── integration/         # Real database (SQLite)
└── e2e/                 # Through HTTP
loadtest/                # k6 load tests
monitoring/              # Prometheus and Grafana config
```

Layers only depend downwards, and the domain is pure Python. `uv run lint-imports`
enforces this.

## Load testing and monitoring

The target load, from the DDIA chapter 1 exercise, is **10M URLs, 100 writes/s and
10,000 reads/s**. The load tests default to a tenth of the request rates; raise
them once you know what your machine can take.

| Piece | Where | What it does |
| --- | --- | --- |
| `url-shortener-admin seed-urls` | `entrypoints/admin.py` | Bulk-inserts URLs (about 100k/s). Seeded code *n* is *n* in base 62, so k6 can compute valid codes without a list |
| k6 scripts | `loadtest/` | `steady.js`: constant read and write rates. `ramp.js`: steps the read rate up to find the breaking point |
| `/metrics` | `entrypoints/metrics.py` | Request counts, latency histograms, requests in progress, DB pool usage |
| Prometheus | http://localhost:9090 | Scrapes the API and Postgres every 5s; receives k6's metrics |
| Grafana | http://localhost:3000 | The "URL shortener" dashboard: API, k6 and Postgres side by side |

### Running a load test

1. Install k6 (`brew install k6`). Without it, `loadtest/run.sh` falls back to the
   k6 Docker image, but then k6 competes with Postgres for the Docker VM's CPUs
   and skews the results.
2. Start Postgres and the monitoring stack, then seed:
   ```sh
   docker compose up -d db prometheus postgres-exporter grafana
   uv run url-shortener-admin seed-urls --count 10000000   # about 2 minutes
   ```
3. Run the API on your machine, without access logs:
   ```sh
   ACCESS_LOG=false uv run url-shortener-api
   ```
4. Open the dashboard at http://localhost:3000 and run a test:
   ```sh
   loadtest/run.sh steady -e SEED_COUNT=10000000                      # 1,000 reads/s, 10 writes/s, 5 minutes
   loadtest/run.sh steady -e SEED_COUNT=10000000 -e READ_RATE=10000 -e WRITE_RATE=100
   loadtest/run.sh ramp   -e SEED_COUNT=10000000 -e MAX_READ_RATE=5000
   ```

Test options, passed as `-e NAME=value`:

| Option | Default | Meaning |
| --- | --- | --- |
| `BASE_URL` | `http://localhost:8000` | API to test |
| `SEED_COUNT` | `1000000` | How many URLs were seeded; reads pick codes from this range |
| `SKEW` | `1` | `1` reads every URL equally often; higher values concentrate reads on a few hot URLs |
| `READ_RATE` / `WRITE_RATE` | `1000` / `10` | Requests per second (`steady.js`) |
| `DURATION` | `5m` | Test length (`steady.js`) |
| `MAX_READ_RATE`, `STEPS`, `STEP_SECONDS` | `5000`, `10`, `60` | Ramp shape (`ramp.js`) |

### Reading the results

- **Percentiles, not averages.** k6's summary and the dashboard show p50, p95, p99
  (and p99.9 in the summary). The mean hides the slow requests users notice.
- **Response time vs. service time.** The API panels time a request from when the
  API starts handling it. k6 times it from when it was *due to be sent*, so it also
  includes waiting in queues. When they diverge, requests are queueing.
- **The load is open-model.** k6 starts requests on schedule even if earlier ones
  haven't finished, like independent users would. If it runs out of workers it
  reports `dropped_iterations`; any drops mean the target rate wasn't reached.
- **Percentiles from histograms are estimates.** Prometheus interpolates within
  histogram buckets, so the API's percentiles are only as precise as the bucket
  edges in `metrics.py`. k6's numbers are exact.

### Caveats

- Everything runs on one machine, so the load generator, API and database compete
  for CPU. Check Docker Desktop's resource settings: with 2 CPUs, Postgres is
  starved long before the API is.
- The API is a single process. Request rates beyond what one Python process can
  serve need more processes (`uvicorn --workers`), which also needs Prometheus'
  multiprocess mode for the metrics.

## Configuration

All configuration comes from environment variables. Locally they are read from
`.env`, which is never committed.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `DATABASE_URL` | yes | | SQLAlchemy database URL |
| `PORT` | no | `8000` | Port the API binds to |
| `HOST` | no | `0.0.0.0` | Interface the API binds to |
| `LOG_LEVEL` | no | `INFO` | Python log level |
| `ACCESS_LOG` | no | `true` | Log every HTTP request. Turn off for load tests: it costs CPU per request |
| `DB_PORT` | no | `5432` | Host port for the local Postgres container (compose only) |

## Twelve-factor

| Factor | How |
| --- | --- |
| I. Codebase | One repo, many deploys |
| II. Dependencies | Declared in `pyproject.toml`, pinned in `uv.lock` |
| III. Config | Environment variables only, read by `config.Settings` |
| IV. Backing services | Attached through URLs such as `DATABASE_URL` |
| V. Build, release, run | `Dockerfile` builds an image; config is added at run time |
| VI. Processes | Stateless processes; all state lives in backing services |
| VII. Port binding | `url-shortener-api` serves HTTP itself on `$PORT` |
| VIII. Concurrency | Scale out by running more processes |
| IX. Disposability | Fast startup, graceful shutdown on SIGTERM (FastAPI lifespan) |
| X. Dev/prod parity | `compose.yaml` runs the same Postgres locally |
| XI. Logs | Written unbuffered to stdout; the environment collects them |
| XII. Admin processes | `url-shortener-admin` runs one-off tasks with the same code and config |
