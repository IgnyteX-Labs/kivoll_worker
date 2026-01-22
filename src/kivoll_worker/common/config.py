"""
Configuration management for kivoll_worker.

This module provides centralized configuration loading, validation,
and access for JSON-based settings.
It supports automatic migration between schema versions,
falling back to bundled defaults on errors,
and resolves user-defined data directory paths and timezones.

.. note::
    ``init_config()`` must be called before ``config()`` or ``data_dir()`` are used.

Example::
    >>> from kivoll_worker.common.config import init_config, config, data_dir
    >>> init_config("data/config.json")
    >>> print(config()["modules"]["weather"]["url"])
    >>> print(data_dir() / "output.db")

See Also:
    - :mod:`kivoll_worker.defaults.config.default.json` for the default schema
    - :mod:`kivoll_worker.common.arguments` for CLI argument parsing
"""

import logging
from datetime import datetime, tzinfo
from importlib.resources import files
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from cliasi import Cliasi
from singlejson import JSONDeserializationError, JSONFile, load

# CLI instance for config-related logging
cli = Cliasi("config")

# ---------------------------------------------------------------------------
# Module-level state (initialized by init_config)
# ---------------------------------------------------------------------------

# The loaded JSONFile instance wrapping the user's config file
_config: JSONFile

# Resolved absolute path to the data directory (from config["paths"]["data"])
_data_dir: Path

# Current config schema version. Increment this when making breaking changes
# to the config structure and add migration logic in __config_migrations().
CURRENT_CONFIG_VERSION: int = 1


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def config() -> Any:
    """
    Return the loaded configuration dictionary.

    :returns: Parsed JSON configuration.
    :rtype: dict[str, Any]
    :raises RuntimeError: When ``init_config()`` was not called.

    Example::
        >>> cfg = config()
        >>> weather_url = cfg["modules"]["weather"]["url"]
    """
    if _config is None or _config.json is None:
        raise RuntimeError("init_config must be called before config()")
    return _config.json


def data_dir() -> Path:
    """
    Return the resolved data directory path.

    :returns: Absolute path where runtime files (databases, heartbeat, cached HTML) live
    :rtype: Path
    :raises RuntimeError: When ``init_config()`` was not called.
    """
    if _data_dir is None:
        raise RuntimeError("init_config must be called before data_dir()")
    return _data_dir


def init_config(config_path: str) -> None:
    """
    Initialize the configuration system by loading the JSON file.

    This function loads the provided config file
    (creating one from defaults if missing), validates its structure, runs migrations,
     and resolves the data directory.

    :param config_path: Path to the config JSON file (absolute or relative).

    .. note::
        When the config file contains malformed JSON,
        it is replaced with the default after a short countdown.
    """
    global _config, _data_dir

    # Load config using singlejson library which handles:
    # - Creating file from default if it doesn't exist
    # - Preserving comments if any (preserve=True)
    # - Validating JSON syntax (strict=True)
    _config = load(
        path=config_path,
        default_data=(
            files("kivoll_worker.defaults") / "config.default.json"
        ).read_text(),
        strict=True,
        load_file=False,  # Don't load yet, we'll do it manually to handle errors
        preserve=True,
    )

    # Attempt to load the config file
    try:
        _config.reload(strict=True)
    except JSONDeserializationError:
        # Config file exists but contains invalid JSON
        # We can recover by reverting to default
        cli.fail(
            f"Config file at {config_path} is malformed JSON.\n"
            f"Will revert to default config."
        )
        __default_config()

    # Run any pending migrations to update old config versions
    __config_migrations()

    # Resolve the data directory from config and ensure it exists
    _data_dir = Path(config()["paths"]["data"]).expanduser().resolve()
    _data_dir.mkdir(parents=True, exist_ok=True)


def __default_config() -> None:
    """
    Revert the configuration to default values.

    :returns: None
    """
    global _config, _data_dir
    cli.warn("Reverting to default config...")
    cli.animate_message_blocking(
        "Writing default config to disk...",
        5,
        message_right="[CTRL-C to cancel]",
    )
    _config.restore_default()
    cli.warn("Config reverted to default.")


def __config_migrations() -> None:
    """
    Run config schema migrations if the version is outdated.

    Config versions are read from ``config()["file"]["version"]``
    and each migration is defined by adding new cases to the match statement.

    :returns: None
    """
    version = config()["file"]["version"]
    try:
        version = int(version)
        match version:
            # Add future migrations here as new cases:
            # case 1:
            #     _migrate_v1_to_v2()
            #     # Fall through to next migration...

            case _ if version == CURRENT_CONFIG_VERSION:
                cli.success(
                    f"Config version {version} is up to date.", verbosity=logging.DEBUG
                )
                return
            case _:
                cli.fail(
                    f"Config version {version} is unknown. Maybe too new?\n"
                    f"Will revert to default config."
                )
                __default_config()
                return
    except ValueError:
        cli.fail(
            f"Config version is not an integer (got {version})\n"
            f"Will revert to default config."
        )
        __default_config()
        return
    except KeyError:
        cli.fail(
            "config.json is malformed, missing 'config.version' key\n"
            "Will revert to default config."
        )
        __default_config()
        return


def get_tz(cli: Cliasi) -> tzinfo | ZoneInfo | None:
    """
    Resolve the configured timezone for scraping operations.

    :param cli: Cliasi instance for logging warnings.
    :returns:
        A :class:`tzinfo` object representing the configured timezone,
        or ``None`` if resolution fails.
    :rtype: tzinfo | ZoneInfo | None

    Example::
        >>> from kivoll_worker.common.config import get_tz
        >>> tz = get_tz(cli)
        >>> now = datetime.now(tz)
    """
    tz_name = str(config().get("general", {}).get("timezone", "")).strip()
    if not tz_name:
        cli.warn("No scrape timezone configured, using local timezone")
        return datetime.now().astimezone().tzinfo
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        cli.warn(f"Invalid timezone '{tz_name}', using local timezone")
        return datetime.now().astimezone().tzinfo
