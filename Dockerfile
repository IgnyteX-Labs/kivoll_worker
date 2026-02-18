# ---- build kivoll_worker ----

# ---- Builder ----
FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim AS builder

LABEL authors="IgnyteX-Labs"
ENV UV_NO_DEV=1
ENV UV_LINK_MODE=copy

RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . .

RUN --mount=type=cache,id=uv-cache,target=/root/.cache/uv,sharing=locked \
    uv build --wheel

RUN chmod +x healthcheck.sh

# ---- Runtime ----
FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_LINK_MODE=copy

WORKDIR /app

COPY --from=builder /app/dist/*.whl /tmp
COPY --from=builder /app/healthcheck.sh /app/healthcheck.sh

RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system /tmp/*.whl && \
    rm -rf /tmp/*.whl

HEALTHCHECK --interval=1m --timeout=10s --retries=3 CMD ["/app/healthcheck.sh"]

CMD [ "uv", "run", "kivoll-schedule", "--verbose" ]
