# ---- Builder ----
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

WORKDIR /app

# Copy local source code instead of cloning from git
COPY pyproject.toml uv.lock ./

COPY deploy/healthcheck.sh /usr/local/bin/healthcheck.sh
RUN chmod +x /usr/local/bin/healthcheck.sh

COPY src/kivoll_worker/__about__.py src/kivoll_worker/

RUN uv sync --no-dev


# ---- Runtime ----
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

COPY --from=builder /app /app

HEALTHCHECK --interval=1m --timeout=10s --start-period=2m --retries=3 CMD /usr/local/bin/healthcheck.sh

CMD [ "uv", "run", "kivoll-schedule", "--verbose" ]
