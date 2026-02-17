# ---- use the Makefile in the TLD to build this image ----

# ---- Builder ----
FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim AS builder

LABEL authors="IgnyteX-Labs"

WORKDIR /app

COPY pyproject.toml uv.lock README.md LICENSE healthcheck.sh ./


RUN --mount=type=cache,id=uv-cache,target=/root/.cache/uv,sharing=locked \
    uv sync --no-dev --frozen --no-install-project


# ---- Runtime ----
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

WORKDIR /app

RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app /app

RUN chmod +x healthcheck.sh

HEALTHCHECK --interval=1m --timeout=10s --retries=3 CMD ["/app/healthcheck.sh"]

RUN --mount=type=cache,id=uv-cache,target=/root/.cache/uv,sharing=locked \
    uv sync --no-dev --locked --no-install-project

# .git is mounted read-only at runtime for version detection
CMD [ "uv", "run", "kivoll-schedule", "--verbose" ]

