# AGENTS.md

Guidance for coding agents (and humans) working in this repository.

This project was created from a skeleton that follows domain-driven design with the
architecture from [Cosmic Python](https://www.cosmicpython.com/), and the
[twelve-factor app](https://12factor.net/) guidelines. Keep to both.

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
uv run my-project-api                # serve the API on $PORT
uv run my-project-admin init-db      # create database tables
docker compose up -d db              # start local Postgres
```

## Where things live

The code is split into **bounded contexts**, one package each, which share a small
kernel and are wired together at the top level.

```
src/my_project/
├── example/                # A bounded context (a working example: copy it, then delete it)
│   ├── domain/             #   Business logic. Pure Python, no I/O, no frameworks.
│   │   ├── model.py        #     Aggregates (subclass shared.domain.Aggregate)
│   │   ├── commands.py     #     Commands: requests to do something (imperative names)
│   │   └── events.py       #     Events: facts that happened (past-tense names)
│   ├── service_layer/      #   Use cases
│   │   ├── handlers.py     #     One function per command/event, plus the registries
│   │   └── unit_of_work.py #     This context's repositories
│   ├── adapters/
│   │   └── orm.py          #     Tables and imperative mappings for this context
│   ├── entrypoints/
│   │   └── api.py          #     FastAPI router: translates HTTP into commands/views
│   └── views.py            #   Read-only queries that bypass the domain (CQRS)
├── shared/                 # Shared kernel: generic building blocks for every context
│   ├── domain.py           #   Aggregate, Command, Event base classes
│   ├── messagebus.py       #   Dispatches commands/events to handlers
│   ├── unit_of_work.py     #   AbstractUnitOfWork, SqlAlchemyUnitOfWork base classes
│   ├── repository.py       #   AbstractRepository, SqlAlchemyRepository
│   ├── orm.py              #   Shared SQLAlchemy registry/metadata, session factory
│   └── api.py              #   FastAPI dependencies: Bus, DbSession
├── entrypoints/            # The running app
│   ├── fastapi_app.py      #   FastAPI app: mounts every context's router; `my-project-api`
│   └── admin.py            #   One-off admin tasks (`my-project-admin`)
├── bootstrap.py            # Composition root: the only module that knows every context
└── config.py               # Settings from environment variables, logging setup
tests/
├── fakes.py                # FakeRepository, reusable by every context's tests
├── conftest.py             # Database fixtures and the `client` fixture for e2e tests
├── shared/                 # Tests for the shared kernel
├── example/                # Tests for one context, split by speed:
│   ├── unit/               #   No I/O. Use fakes.
│   ├── integration/        #   Real database (in-memory SQLite)
│   └── e2e/                #   Through HTTP (the `client` fixture)
└── e2e/                    # App-wide tests (health check)
```

## Architecture rules

`lint-imports` enforces all of these; the contracts are in `pyproject.toml`.

1. **Top-level layers:** `entrypoints → bootstrap → contexts → shared`. Each only
   imports from layers to its right.
2. **Contexts are independent.** A context never imports another context. What they
   share lives in `shared/`. Contexts communicate through events on the message bus.
   If another context needs to react to an event, define that event in `shared/` as
   part of the published language, not in either context.
3. **Inside each context:** `entrypoints → views | service_layer → adapters → domain`.
   `views` and `service_layer` must not import each other.
4. **Domain is pure Python.** No SQLAlchemy, FastAPI, pydantic or `config` in any
   `domain` package. The ORM maps domain classes *imperatively* in `adapters/orm.py`.
5. **Entrypoints are thin.** They build a command and call `bus.handle(command)`, or
   call a function in the context's `views.py`. They never touch repositories or the
   ORM.
6. **Handlers get their dependencies injected** by `bootstrap.py`, matched by
   parameter name (`uow`, plus any adapters you add). Never import a concrete
   adapter inside a handler.

## Adding a feature to a context

Work from the inside out, writing tests as you go. `example/` shows each step.

1. **Domain:** add or extend an aggregate in `domain/model.py`. Record things that
   happened with `self.events.append(SomethingHappened(...))`. Unit test it.
2. **Commands/events:** add `@dataclass` classes to `domain/commands.py` /
   `domain/events.py`, subclassing `shared.domain.Command` / `Event`.
3. **Persistence:** add a `Table` and a `mapper_registry.map_imperatively(...)` call in
   `adapters/orm.py`. For a new aggregate, declare a repository on the context's
   `AbstractUnitOfWork`, create it in `SqlAlchemyUnitOfWork._create_repositories`,
   and add it to the `FakeUnitOfWork` in the context's `tests/.../unit/test_handlers.py`.
   Table names must be unique across all contexts.
4. **Handler:** write a function in `service_layer/handlers.py` taking the message and
   the dependencies it needs, and register it in `COMMAND_HANDLERS` or
   `EVENT_HANDLERS`. Test it through `bootstrap.bootstrap(start_orm=False, ...)` with
   a `FakeUnitOfWork`.
5. **Reads:** add a query function to `views.py`, taking a `Session`.
6. **Entrypoint:** add a route to `entrypoints/api.py`. Take `bus: Bus` to send
   commands and `session: DbSession` for views. Map domain exceptions to HTTP
   errors there. Add an e2e test using the `client` fixture.

## Adding a bounded context

1. Copy `src/my_project/example/` to `src/my_project/<context>/` and
   `tests/example/` to `tests/<context>/`, then replace the Thing code with your own.
   Rename the tables.
2. In `bootstrap.py`, import the context's `orm`, `handlers` and `unit_of_work`. Call
   its `start_mappers()` in `start_mappers`. Add a `<context>_uow` parameter to
   `bootstrap`, add an entry to `contexts`, and add its uow to `uows`.
3. In `entrypoints/fastapi_app.py`, `include_router` the context's router.
4. In `pyproject.toml`, add the context to the top-level layers contract:
   `"my_project.example | my_project.<context>"`. The other contracts pick it up
   automatically.
5. Once you have real contexts, delete `example/` and `tests/example/` and remove
   their references from the three files above.

## Conventions

- **Commands vs events:** a command has exactly one handler, and its exceptions
  propagate to the caller. An event can have zero or more handlers, and their
  exceptions are logged and swallowed.
- **Transactions:** always use `with uow:` and call `uow.commit()` explicitly.
  Leaving the block without committing rolls back.
- **New infrastructure** (email, message broker, external API): define an abstract
  class and its real implementation in the context's `adapters/` (or in `shared/`
  if several contexts need it), with a fake in the tests. Add it to that context's
  dependencies in `bootstrap.py`.
- **Config:** add a field to `Settings` in `config.py`, and document it in
  `.env.example` and in the README's configuration table. Never read `os.environ`
  anywhere else, and never hard-code environment-specific values (URLs, credentials,
  hostnames). Only settings with safe defaults for every environment get a default.
- **Logging:** use `logger = logging.getLogger(__name__)` at module level. Never
  write log files, and never configure logging outside `config.configure_logging`.
- **State:** processes are stateless. Store anything that must survive a request in
  a backing service (the database), not in memory or on local disk.
- **Admin tasks:** add them to `COMMANDS` in `entrypoints/admin.py` rather than
  writing standalone scripts.

## Style

- Python 3.12+. Use modern syntax: `list[int]`, `X | None`, `type` aliases, PEP 695
  generics (`class Repo[T]:`).
- Formatting and import order are ruff's job. Don't hand-format.
- Type-annotate function signatures in `src/`.
- Prefer plain functions and dataclasses. Use classes where there is state or an
  interface (aggregates, repositories, unit of work).
- Abstract interfaces are `abc.ABC` classes named `Abstract...`, with concrete
  implementations named after their technology (`SqlAlchemy...`) and fakes named
  `Fake...`.
- Import modules rather than names within a context
  (`from my_project.example.domain import commands`, then `commands.CreateThing`).
  When a module name clashes across contexts, alias it with the context name
  (`from my_project.example.adapters import orm as example_orm`).
- Keep comments sparse. Explain *why*, not what.
- Test names describe behaviour: `test_cannot_create_a_thing_twice`.
