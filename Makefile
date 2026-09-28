# Load testing shortcuts. Run `make` to list them. Override any variable on the
# command line, e.g. `make api WORKERS=8` or `make steady READ_RATE=3000`.
#
# DATABASE_URL and DB_PORT come from .env, as for the rest of the app.

# URLs seeded, and the range load tests read from
SEED_COUNT ?= 1000000
# Uniform reads at 1; higher concentrates reads on a few hot URLs
SKEW ?= 1

# API processes, and each one's connection pool. 5 + 5 per worker keeps 8 workers
# (80 connections) under Postgres' max_connections of 100.
WORKERS ?= 1
POOL_SIZE ?= 5
MAX_OVERFLOW ?= 5

# steady.js
READ_RATE ?= 1000
WRITE_RATE ?= 10
DURATION ?= 5m

# ramp.js and bench
MAX_READ_RATE ?= 8000
STEPS ?= 8
STEP_SECONDS ?= 15
BENCH_WORKERS ?= 1 2 4 8

K6_ENV = -e SEED_COUNT=$(SEED_COUNT) -e SKEW=$(SKEW)
POOL_ENV = DB_POOL_SIZE=$(POOL_SIZE) DB_MAX_OVERFLOW=$(MAX_OVERFLOW)

.DEFAULT_GOAL := help
.PHONY: help stack-up stack-down seed api steady ramp bench dashboard

help: ## List the targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*## "}; {printf "  make %-11s %s\n", $$1, $$2}'

stack-up: ## Start Postgres, Prometheus, Grafana and the Postgres exporter
	docker compose up -d db prometheus postgres-exporter grafana

stack-down: ## Stop them (data is kept; `docker compose down -v` deletes it)
	docker compose stop db prometheus postgres-exporter grafana

seed: ## Bulk-insert SEED_COUNT URLs (safe to re-run)
	uv run url-shortener-admin seed-urls --count $(SEED_COUNT)

api: ## Run the API for load tests: WORKERS processes, no access log
	ACCESS_LOG=false WEB_CONCURRENCY=$(WORKERS) $(POOL_ENV) uv run url-shortener-api

steady: ## Constant load: READ_RATE reads/s and WRITE_RATE writes/s for DURATION
	loadtest/run.sh steady $(K6_ENV) -e READ_RATE=$(READ_RATE) \
		-e WRITE_RATE=$(WRITE_RATE) -e DURATION=$(DURATION)

ramp: ## Step reads up to MAX_READ_RATE to find the breaking point
	loadtest/run.sh ramp $(K6_ENV) -e MAX_READ_RATE=$(MAX_READ_RATE) \
		-e STEPS=$(STEPS) -e STEP_SECONDS=$(STEP_SECONDS) -e WRITE_RATE=$(WRITE_RATE)

bench: ## Ramp each of BENCH_WORKERS in turn and summarize (starts the API itself)
	$(POOL_ENV) MAX_READ_RATE=$(MAX_READ_RATE) STEPS=$(STEPS) \
		STEP_SECONDS=$(STEP_SECONDS) SEED_COUNT=$(SEED_COUNT) \
		loadtest/bench.sh $(BENCH_WORKERS)

dashboard: ## Open the Grafana dashboard
	open http://localhost:3000
