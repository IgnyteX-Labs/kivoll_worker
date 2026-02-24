# ---- use the Makefile in the TLD to build this image ----
# Runtime mounts (via Makefile):
#   -v $(PWD)/src:/app/src       source code (project is installed from here at startup)
#   -v $(PWD)/data:/app/data     persistent data
#   -v $(PWD)/.git:/app/.git     git history for setuptools-scm version detection


# ---- Stage 1: Pre-install all runtime dependencies ----
# This layer is invalidated only when pyproject.toml / uv.lock change,
# so builds that only edit source files skip all dependency work entirely.
FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim AS deps

ENV UV_NO_DEV=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock README.md LICENSE ./

RUN --mount=type=cache,id=uv-cache,target=/root/.cache/uv,sharing=locked \
    uv sync --frozen --no-install-project


# ---- Stage 2: Runtime ----
FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim

LABEL authors="IgnyteX-Labs"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_DEV=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# All dependencies are already installed — no network access needed for them.
# The project package itself is NOT installed here; uv run installs it at
# startup from the mounted src/ (fast: no deps to resolve or download).
COPY --from=deps /app/.venv /app/.venv

# Manifests stay in the image; source is supplied via the runtime mount.
COPY pyproject.toml uv.lock README.md LICENSE healthcheck.sh ./

RUN chmod +x healthcheck.sh

HEALTHCHECK --interval=1m --timeout=10s --retries=3 CMD ["/app/healthcheck.sh"]

CMD ["uv", "run", "kivoll-schedule", "--verbose"]