# ---- use the Makefile in the TLD to build this image ----

# ---- Builder ----
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

LABEL authors="IgnyteX-Labs"

WORKDIR /app

# Copy local source code instead of cloning from git
COPY pyproject.toml uv.lock ./


COPY src/kivoll_worker/__about__.py src/kivoll_worker/
COPY healthcheck.sh .

RUN uv sync --no-dev --frozen


# ---- Runtime ----
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

COPY --from=builder /app /app

RUN chmod +x healthcheck.sh
HEALTHCHECK --interval=1m --timeout=10s --retries=3 CMD ["/app/healthcheck.sh"]

CMD [ "uv", "run", "kivoll-schedule", "--verbose" ]
