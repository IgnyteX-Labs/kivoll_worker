import json
import subprocess
import time
import uuid
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from testcontainers.core.container import DockerContainer
from testcontainers.core.network import Network

from conftest import _build_container, _wait_for_db_ready

DATABASE_IMG = "ghcr.io/ignytex-labs/kivoll_db:0.1.0"

# Fixed sentinel version used when building the worker image for tests.
# Using a constant keeps tests hermetic (independent of the local git state)
# and validates that the VERSION build-arg is correctly propagated through
# SETUPTOOLS_SCM_PRETEND_VERSION all the way to the installed package.
TEST_VERSION = "0.0.0"


@dataclass(frozen=True)
class BuiltImage:
    tag: str
    stdout: str
    stderr: str
    ok: bool


PROJECT_ROOT = Path(__file__).parent.parent
BUILD_CONTEXT = PROJECT_ROOT


def test_dockerfile_general(built_db_image):
    """General tests on the Dockerfile: check CMD and healthcheck."""
    if not built_db_image.ok:
        pytest.skip("Docker build failed; skipping inspection test")

    result = subprocess.run(
        ["docker", "inspect", built_db_image.tag], capture_output=True, text=True
    )
    assert result.returncode == 0, f"Inspect failed: {result.stderr}"

    data = json.loads(result.stdout)
    config = data[0]["Config"]

    # Check CMD
    assert config["Cmd"] == ["kivoll-schedule", "--verbose"]

    # Check healthcheck
    healthcheck = config.get("Healthcheck")
    assert healthcheck is not None
    assert healthcheck["Test"] == ["CMD", "/app/healthcheck.sh"]


@pytest.fixture(scope="session")
def get_network() -> Generator[Network, Any, None]:
    network = Network()
    network.create()
    yield network
    network.remove()


@pytest.fixture(scope="session")
def postgres_container(
    test_env: dict[str, str], get_network: Network
) -> Generator[DockerContainer, Any, None]:
    container = _build_container(DATABASE_IMG, test_env)
    container.with_network(get_network).with_network_aliases("db")
    with container:
        host = container.get_container_host_ip()
        port = int(container.get_exposed_port(5432))
        _wait_for_db_ready(
            host,
            port,
            test_env["POSTGRES_USER"],
            test_env["POSTGRES_PASSWORD"],
            test_env["POSTGRES_DB"],
        )
        yield container


@pytest.fixture(scope="session")
def db_image_tag() -> str:
    suffix = uuid.uuid4().hex[:8]
    return f"kivoll-worker-test-{suffix}"


@pytest.fixture(scope="session")
def built_db_image(
    db_image_tag: str,
) -> Generator[BuiltImage, Any, None]:
    # Run docker build and record output; don't fail the fixture immediately.
    result = subprocess.run(
        [
            "docker",
            "build",
            "--build-arg",
            f"VERSION={TEST_VERSION}",
            "-t",
            db_image_tag,
            str(BUILD_CONTEXT),
        ],
        capture_output=True,
        text=True,
    )

    ok = result.returncode == 0

    # Yield a BuiltImage that indicates whether the build succeeded.
    yield BuiltImage(
        tag=db_image_tag, stdout=result.stdout, stderr=result.stderr, ok=ok
    )

    # Attempt to remove the image (best-effort cleanup).
    subprocess.run(
        ["docker", "rmi", "-f", db_image_tag], capture_output=True, text=True
    )


@pytest.mark.slow
@pytest.mark.integration
def test_worker_image_gets_healthy(
    built_db_image, postgres_container, test_env: dict[str, str], get_network: Network
):
    # Skip this integration test if the image build failed.
    if not built_db_image.ok:
        pytest.skip("Docker build failed; skipping integration test")

    container = _build_container(built_db_image.tag, test_env)
    container.with_network(get_network)
    container.with_env("DB_HOST", "db:5432")
    try:
        container.start()
        # Wait for health status to be healthy
        deadline = time.time() + 70
        # the first health check is after 60 seconds
        underlying_container = container.get_wrapped_container()
        while time.time() < deadline:
            underlying_container.reload()
            if underlying_container.status == "exited":
                break
            if underlying_container.health == "healthy":
                return
            time.sleep(1)
        try:
            logs = container.get_logs()
        except Exception as exc:
            logs = f"Could not retrieve logs: {exc}"
        pytest.fail(f"Container did not become healthy in time {logs}")
    finally:
        container.stop()


@pytest.mark.slow
@pytest.mark.integration
def test_built_dockerfile(built_db_image: BuiltImage):
    # Skip assertions if build failed; other tests may handle failure details.
    if not built_db_image.ok:
        pytest.fail(
            "Docker build failed; skipping dockerfile tests\n"
            f"Error: {built_db_image.stderr}"
        )

    assert built_db_image.tag, "Built image tag should not be empty"
    inspect = subprocess.run(
        ["docker", "image", "inspect", built_db_image.tag],
        capture_output=True,
        text=True,
    )
    assert inspect.returncode == 0, (
        f"Built image {built_db_image.tag} not found.\n"
        f"stdout:\n{inspect.stdout}\n"
        f"stderr:\n{inspect.stderr}\n"
    )
    assert built_db_image.stdout or built_db_image.stderr, "docker build output missing"


@pytest.fixture(scope="session")
def container_package_installed(built_db_image: BuiltImage) -> bool:
    """Return True if kivoll_worker is importable inside the built image.

    Skips automatically if the image build itself failed.
    """
    if not built_db_image.ok:
        pytest.skip("Docker build failed; skipping package installation check")

    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            built_db_image.tag,
            "python",
            "-c",
            "import kivoll_worker",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.returncode == 0


@pytest.mark.slow
@pytest.mark.integration
def test_container_package_installed(
    built_db_image: BuiltImage, container_package_installed: bool
):
    """Test that the kivoll_worker package is importable inside the container."""
    assert container_package_installed, (
        "kivoll_worker is not importable in the container — "
        "the wheel may not have been installed correctly.\n"
        f"Build stderr: {built_db_image.stderr}"
    )


@pytest.mark.slow
@pytest.mark.integration
def test_container_version_matches_project(
    built_db_image: BuiltImage, container_package_installed: bool
):
    """Test that the version baked into the image matches the TEST_VERSION build-arg.

    This validates the full chain:
      --build-arg VERSION=<ver>  →  SETUPTOOLS_SCM_PRETEND_VERSION  →  installed package
    The entry-point is invoked directly from the venv (no `uv run` overhead)
    because the runtime image does not have a project context for uv to resolve.
    """
    if not built_db_image.ok:
        pytest.skip("Docker build failed; skipping version test")
    if not container_package_installed:
        pytest.skip("Package not importable; skipping version test")

    # kivoll-scrape is on PATH via /app/.venv/bin (set in the Dockerfile).
    result = subprocess.run(
        ["docker", "run", "--rm", built_db_image.tag, "kivoll-scrape", "--version"],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, (
        f"Failed to get version from container: {result.stderr}"
    )

    # Output is typically "kivoll_worker <version>"
    container_version = result.stdout.strip().split()[-1]

    assert container_version == TEST_VERSION, (
        f"Container version '{container_version}' "
        f"does not match expected build version '{TEST_VERSION}'"
    )
