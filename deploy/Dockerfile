# ---- Builder ----
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

WORKDIR /app

# Copy local source code instead of cloning from git
COPY pyproject.toml uv.lock ./


COPY src/kivoll_worker/__about__.py src/kivoll_worker/

RUN uv sync --no-dev --frozen


# ---- Runtime ----
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

COPY --from=builder /app /app

RUN chmod +x deploy/healthcheck.sh
HEALTHCHECK --interval=1m --timeout=10s --start-period=2m --retries=3 CMD deploy/healthcheck.sh

CMD [ "uv", "run", "kivoll-schedule", "--verbose" ]
