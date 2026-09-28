# AGENTS.md

Guidance for coding agents (and humans) working in this repository.

A URL shortener used as a playground for *Designing Data-Intensive Applications*. It
uses a layered architecture loosely based on [Cosmic Python](https://www.cosmicpython.com/),
simplified for a single bounded context (no message bus or unit of work), and follows
the [twelve-factor app](https://12factor.net/) guidelines. Keep to both.

## Commands

Run all of these before considering a change done:

```sh
uv run ruff format .     # format
uv run ruff check .      # lint (add --fix to auto-fix)
uv run mypy              # type check
uv run lint-imports      # enforce the architecture rules below
uv run pytest            # tests
```

Other useful commands:

```sh
uv add <package>                     # add a runtime dependency
uv add --group dev <package>         # add a dev-only dependency
uv run url-shortener-api                # serve the API on $PORT
uv run url-shortener-admin init-db      # create database tables
uv run url-shortener-admin seed-urls --count 1000000  # bulk-insert URLs for load tests
docker compose up -d db              # start local Postgres
make steady / make ramp / make bench  # load tests (run `make` to list them)
```

## Where things live

```
src/url_shortener/
├── domain/
│   └── model.py            # ShortURL and short code generation. Pure Python, no I/O.
├── service_layer/
│   └── services.py         # Use cases that change state: one function each, taking a Session
├── adapters/
│   ├── orm.py              # Tables, imperative mappings, create_tables, session factory
│   └── cache.py            # In-process LRU cache for reads
├── views.py                # Read-only queries that bypass the domain (CQRS)
├── entrypoints/
│   ├── fastapi_app.py      #   FastAPI app, lifespan; `url-shortener-api`
│   ├── api.py              #   Routes: translate HTTP into service calls and views
│   ├── dependencies.py     #   FastAPI dependencies (DbSession, ReadEngine, ReadCache)
│   ├── metrics.py          #   Prometheus middleware, /metrics, pool and process metrics
│   └── admin.py            #   One-off admin tasks (`url-shortener-admin`)
└── config.py               # Settings from environment variables, logging setup
tests/
├── conftest.py             # Database fixtures and the `client` fixture for e2e tests
├── unit/                   # No I/O
├── integration/            # Real database (in-memory SQLite)
└── e2e/                    # Through HTTP (the `client` fixture)
loadtest/                   # k6 scripts, runner, bench.sh and analyze.py
monitoring/                 # Prometheus config, Grafana provisioning and dashboard
```

## Architecture rules

`lint-imports` enforces these; the contracts are in `pyproject.toml`.

1. **Layers:** `entrypoints → views | service_layer → adapters → domain`. Each only
   imports from layers to its right. `views` and `service_layer` must not import
   each other.
2. **Domain is pure Python.** No SQLAlchemy, FastAPI, pydantic or `config` in
   `domain`. The ORM maps domain classes *imperatively* in `adapters/orm.py`.
3. **Entrypoints are thin.** Routes validate input, call a function in
   `service_layer/services.py` or `views.py`, and map exceptions to HTTP errors.

## Adding a feature

Work from the inside out, writing tests as you go.

1. **Domain:** add or extend a class in `domain/model.py`. Unit test it.
2. **Persistence:** add a `Table` and a `mapper_registry.map_imperatively(...)` call in
   `adapters/orm.py`.
3. **Writes:** add a function to `service_layer/services.py` taking a `Session` and
   plain arguments. It owns the transaction: call `session.commit()` itself.
   Integration test it with the `sqlite_session_factory` and `mappers` fixtures.
4. **Reads:** add a query function to `views.py`, taking the read `Engine` and
   opening a connection only around its query. Integration test it against an
   autocommit engine.
5. **Entrypoint:** add a route to `entrypoints/api.py`, taking `session: DbSession`
   for writes or `engine: ReadEngine` for reads (plus `read_cache: ReadCache` for
   cached reads). Add an e2e test using the `client` fixture.

## Conventions

- **Sessions and connections:** a session per request from `DbSession` (writes);
  views open a connection from `ReadEngine` (reads). FastAPI runs sync routes in a
  thread pool and neither is thread-safe, so never store one in a module global or
  on `app.state`. The engines and session factory are safe to share.
- **Take connections late, release them early:** never check out a connection in a
  dependency's setup. FastAPI runs the setup and the route on separate thread-pool
  threads, so under load requests hold every connection while waiting for a thread,
  and every thread waits for a connection: a deadlock until the pool times out.
- **Reads are autocommit:** a view's query runs as a single statement, with no
  BEGIN/ROLLBACK (three round trips become one). If a view runs several queries
  that must agree with each other, run them in `with engine.begin() as connection:`.
- **Transactions:** service functions commit explicitly. Prefer letting database
  constraints catch conflicts (catch `IntegrityError`, roll back, raise a domain
  exception) over check-then-write, which races under concurrency.
- **New infrastructure** (cache, message broker, external API): put the client in
  `adapters/`, create it in the FastAPI lifespan, and pass it to services as an
  argument.
- **Config:** add a field to `Settings` in `config.py`, and document it in
  `.env.example` and in the README's configuration table. Never read `os.environ`
  anywhere else, and never hard-code environment-specific values (URLs, credentials,
  hostnames). Only settings with safe defaults for every environment get a default.
- **Logging:** use `logger = logging.getLogger(__name__)` at module level. Never
  write log files, and never configure logging outside `config.configure_logging`.
- **Caches:** an in-process cache (`adapters/cache.py`) is only for data that never
  changes, like short URLs: each worker has its own copy, and nothing tells the
  others when an entry changes. Never cache "not found". Anything mutable needs
  invalidation or a shared cache.
- **State:** processes are stateless. Store anything that must survive a request in
  a backing service (the database), not in memory or on local disk.
- **Admin tasks:** add them as subcommands in `entrypoints/admin.py` rather than
  writing standalone scripts.
- **Metrics:** label by route template, never by raw path or user input, to keep
  the number of time series bounded.

## Style

- Python 3.12+. Use modern syntax: `list[int]`, `X | None`, `type` aliases, PEP 695
  generics (`class Repo[T]:`).
- Formatting and import order are ruff's job. Don't hand-format.
- Type-annotate function signatures in `src/`.
- Prefer plain functions and dataclasses. Use classes where there is state or an
  interface.
- Import modules rather than names (`from url_shortener.domain import model`, then
  `model.ShortURL`).
- Keep comments sparse. Explain *why*, not what.
- Test names describe behaviour: `test_cannot_reuse_a_taken_short_code`.
