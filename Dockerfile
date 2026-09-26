# Build stage: https://12factor.net/build-release-run
# The image is the build artifact; config is supplied at run time via env vars.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml uv.lock README.md LICENSE ./
RUN uv sync --locked --no-install-project

COPY src ./src
RUN uv sync --locked

ENV PATH="/app/.venv/bin:$PATH"

RUN useradd --create-home app
USER app

EXPOSE 8000

# Exec form so the process receives SIGTERM and shuts down gracefully
CMD ["url-shortener-api"]
