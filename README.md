# url-shortener

A foundation for Python backend services. It follows domain-driven design, with
code split into bounded contexts that each use the layered architecture from
[Cosmic Python](https://www.cosmicpython.com/) (domain, service layer, adapters,
entrypoints), and the [twelve-factor app](https://12factor.net/) guidelines. It
ships with FastAPI, SQLAlchemy 2, Postgres, uv, Docker, and enforced code style and
architecture rules.

It includes one working example context (`example`, managing "Things") that shows a
complete slice from domain to HTTP. Copy it to create your own contexts, then delete
it. For the architecture, conventions and step-by-step guides to adding features and
contexts, see [AGENTS.md](AGENTS.md).

## Starting a new project from this skeleton

Prerequisites: [uv](https://docs.astral.sh/uv/), Docker, and the
[GitHub CLI](https://cli.github.com/).

1. **Create a repository from the template.** This gives you a new repository with
   a fresh history, cloned locally:
   ```sh
   gh repo create order-service --private --template nicomellon/python-package-skeleton --clone
   cd order-service
   ```
   Or click "Use this template" on the
   [GitHub page](https://github.com/nicomellon/python-package-skeleton), then clone
   the new repository.
2. **Rename the project.** This replaces `url-shortener` / `url_shortener` everywhere,
   renames `src/url_shortener`, and then deletes the script:
   ```sh
   python3 scripts/rename_project.py order-service
   ```
3. **Fill in the metadata:** `description` and `authors` in `pyproject.toml`, the
   year and copyright holder in `LICENSE`, and the top of this README. The project is
   MIT licensed; if you want a different licence, change `license` in
   `pyproject.toml` and replace `LICENSE` to match.
4. **Install dependencies:**
   ```sh
   uv sync
   ```
5. **Create your local config:**
   ```sh
   cp .env.example .env
   ```
   If port 5432 is already in use on your machine, set `DB_PORT` (e.g. `55432`) in
   `.env` and change the port in `DATABASE_URL` to match.
6. **Start Postgres and create the tables:**
   ```sh
   docker compose up -d db
   uv run url-shortener-admin init-db
   ```
7. **Check that everything passes:**
   ```sh
   uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run lint-imports && uv run pytest
   ```
8. **Run the API** and open http://localhost:8000/docs to try the example context's
   endpoints:
   ```sh
   uv run fastapi dev src/url_shortener/entrypoints/fastapi_app.py --port 8000
   ```
9. **Commit and push** the renamed project:
   ```sh
   git add . && git commit -m "Set up project from python-package-skeleton" && git push
   ```
10. **Create your first bounded context** by following "Adding a bounded context"
    in [AGENTS.md](AGENTS.md). Delete the example context once you no longer need it
    as a reference.

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
├── example/             # A bounded context (one package per context)
│   ├── domain/          #   Pure business logic: aggregates, commands, events
│   ├── service_layer/   #   Handlers, unit of work
│   ├── adapters/        #   ORM mappings, other infrastructure
│   ├── entrypoints/     #   FastAPI router
│   └── views.py         #   Read-only queries (CQRS)
├── shared/              # Shared kernel: base classes, message bus, repositories
├── entrypoints/         # The app: FastAPI app, admin CLI
├── bootstrap.py         # Wires every context into the message bus
└── config.py            # Settings from environment variables, logging setup
tests/
├── shared/              # Shared kernel tests
├── example/             # One folder per context: unit/, integration/, e2e/
└── e2e/                 # App-wide tests
```

Contexts never import each other, and each context's layers only depend downwards.
`uv run lint-imports` enforces this.

## Configuration

All configuration comes from environment variables. Locally they are read from
`.env`, which is never committed.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `DATABASE_URL` | yes | | SQLAlchemy database URL |
| `PORT` | no | `8000` | Port the API binds to |
| `HOST` | no | `0.0.0.0` | Interface the API binds to |
| `LOG_LEVEL` | no | `INFO` | Python log level |
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
