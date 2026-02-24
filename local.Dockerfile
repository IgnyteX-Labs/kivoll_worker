# ---- use the Makefile in the TLD to build this image ----
# Runtime mounts (via Makefile):
#   -v $(PWD)/src:/app/src       source code (overlays the COPY'd src/ below)
#   -v $(PWD)/data:/app/data     persistent data
#   -v $(PWD)/.git:/app/.git     git history (provides real _version.py via the src/ mount)


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
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"
# Expose the pre-built venv so entry points are available without a prefix
# Warning: This path does not contain useful stuff yet!

WORKDIR /app

# All dependencies are already installed — no network access needed for them.
COPY --from=deps /app/.venv /app/.venv

# Manifests stay in the image; source is supplied via the runtime mount.
COPY pyproject.toml uv.lock README.md LICENSE healthcheck.sh ./

# Copy src/ so the editable project install below has something to work with.
# At runtime, src/ is volume-mounted over this copy, providing live code
# without any reinstall step on every container start.
COPY src/ ./src/

# Install the project itself into the venv.
# uv sync without --no-install-project installs the local project in editable
# mode by default (writes a .pth file pointing to /app/src). The runtime
# mount overlays /app/src with live code, so the editable install transparently
# picks up any local changes without reinstalling.
# SETUPTOOLS_SCM_PRETEND_VERSION suppresses the "no .git" error at build time;
# the real _version.py is provided by the mounted src/ at runtime.
RUN --mount=type=cache,id=uv-cache,target=/root/.cache/uv,sharing=locked \
    SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0+dev uv sync --frozen

RUN chmod +x healthcheck.sh

HEALTHCHECK --interval=1m --timeout=10s --retries=3 CMD ["/app/healthcheck.sh"]

# Invoke the entry point directly from the venv — no `uv run` overhead
CMD ["kivoll-schedule", "--verbose"]