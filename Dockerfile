# ---- build kivoll_worker ----

# ---- Builder ----
FROM ghcr.io/astral-sh/uv:python3.13-trixie-slim AS builder

LABEL authors="IgnyteX-Labs"

WORKDIR /app

COPY . .

RUN chmod +x healthcheck.sh

CMD [ "uv", "sync", "--no-dev", "--frozen" ]


# ---- Runtime ----
FROM ghcr.io/astral-sh/uv:python3.13-trixie-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY --from=builder /app /app


HEALTHCHECK --interval=1m --timeout=10s --retries=3 CMD ["/app/healthcheck.sh"]

CMD [ "uv", "run", "kivoll-schedule", "--verbose" ]
