# ---- Stage 1: Resolve & pre-install all runtime dependencies ----
# This layer is invalidated only when pyproject.toml / uv.lock change,
# so repeat builds that only touch source files skip all dependency work.
FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim AS deps

ENV UV_NO_DEV=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Copy only the dependency manifests (and files referenced by pyproject.toml).
# The project source is intentionally excluded here.
COPY pyproject.toml uv.lock README.md LICENSE ./

RUN --mount=type=cache,id=uv-cache,target=/root/.cache/uv,sharing=locked \
    uv sync --frozen --no-install-project


# ---- Stage 2: Build the distributable wheel ----
FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim AS builder

# VERSION is a required build arg
ARG VERSION
RUN test -n "${VERSION}" || \
    { echo "ERROR: VERSION build arg is required. Pass --build-arg VERSION=x.y.z" \
    >&2; exit 1; }
# SETUPTOOLS_SCM_PRETEND_VERSION lets setuptools-scm work without git.
ENV SETUPTOOLS_SCM_PRETEND_VERSION=${VERSION}

WORKDIR /app

# uv.lock is intentionally omitted: `uv build` calls the build backend directly
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/

RUN --mount=type=cache,id=uv-cache,target=/root/.cache/uv,sharing=locked \
    uv build --wheel


# ---- Stage 3: Runtime ----
FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim

LABEL authors="IgnyteX-Labs"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_DEV=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"
# Expose the pre-built venv so entry points are available without a prefix

WORKDIR /app

# All dependencies are already installed — no network access needed for them
COPY --from=deps /app/.venv /app/.venv
COPY --from=builder /app/dist /tmp/dist

# Install only the project package itself into the pre-populated venv.
# --no-deps means zero downloads: uv just lays down the package files & scripts.
RUN --mount=type=cache,id=uv-cache,target=/root/.cache/uv,sharing=locked \
    uv pip install --no-deps /tmp/dist/*.whl \
    && rm -rf /tmp/dist

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD ["kivoll-healthcheck"]

# Invoke the entry point directly from the venv — no `uv run` overhead
CMD ["kivoll-schedule", "--verbose"]