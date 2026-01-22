# ---- Builder ----
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

WORKDIR /app

# Copy local source code instead of cloning from git
COPY . .

# Remove data directory to ensure clean state
RUN rm -rf data/

RUN uv sync --no-dev --frozen


# ---- Runtime ----
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=builder /app /app
COPY deploy/common/healthcheck.sh /usr/local/bin/healthcheck.sh
RUN chmod +x /usr/local/bin/healthcheck.sh

HEALTHCHECK --interval=1m --timeout=10s --start-period=2m --retries=3 CMD /usr/local/bin/healthcheck.sh

CMD [ "uv", "run", "kivoll-schedule", "--verbose" ]
