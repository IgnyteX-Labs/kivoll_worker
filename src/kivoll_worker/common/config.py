"""
Config helpers for kivoll_worker.
"""

import logging
from importlib.resources import files
from pathlib import Path
from typing import Any

from cliasi import Cliasi
from singlejson import JSONDeserializationError, JSONFile, load

cli = Cliasi("config")

# Internal storage for the loaded config and resolved data directory
_config: JSONFile
_data_dir: Path
"""
Main config file instance
"""

CURRENT_CONFIG_VERSION: int = 1


def config() -> Any:
    """Return the loaded config JSON. Raises if init_config was not run."""
    if _config is None or _config.json is None:
        raise RuntimeError("init_config must be called before config()")
    return _config.json


def data_dir() -> Path:
    """Return the resolved data directory. Raises if init_config was not run."""
    if _data_dir is None:
        raise RuntimeError("init_config must be called before data_dir()")
    return _data_dir


def init_config(config_path: str) -> None:
    """
    Load the config file from the given path

    :param config_path: Path to the config file
    """
    global _config, _data_dir

    _config = load(
        path=config_path,
        default_data=(
            files("kivoll_worker.defaults") / "config.default.json"
        ).read_text(),
        strict=True,
        load_file=False,
        preserve=True,
    )
    # This will validate the default config but not load the file yet
    try:
        _config.reload()
    except JSONDeserializationError:
        # We can only recover from malformed json
        # If the default is malformed we do not catch it and just display the error
        cli.fail(
            f"Config file at {config_path} is malformed JSON.\n"
            f"Will revert to default config."
        )
        __default_config()

    __config_migrations()
    # Try to get the data directory
    _data_dir = Path(config()["paths"]["data"]).expanduser().resolve()
    _data_dir.mkdir(parents=True, exist_ok=True)


def __default_config() -> None:
    """
    Revert to default config
    """
    global _config, _data_dir
    cli.warn("Reverting to default config...")
    cli.animate_message_blocking(
        "Writing default config to disk...",
        3,
        message_right="[CTRL-C to cancel]",
    )
    _config.restore_default()
    cli.warn("Config reverted to default.")


def __config_migrations() -> None:
    """
    Run config migrations
    """
    version = config()["file"]["version"]
    try:
        version = int(version)
        match version:
            # Add future migrations here

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
