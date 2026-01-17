"""
This file handles failures while program is running
"""

import logging
from importlib.resources import files
from time import time

from cliasi import Cliasi
from singlejson import JSONDeserializationError, JSONFile, load

from . import config

cli = Cliasi("ERROR", messages_stay_in_one_line=False)

_errors: JSONFile

CURRENT_ERRORS_VERSION: int = 1


def init_errors_db() -> None:
    """
    Initialize the errors database
    """
    global _errors

    _errors = load(
        config.data_dir() / "errors.json",
        default_data=(
            files("kivoll_worker.defaults") / "errors.default.json"
        ).read_text(),
        strict=True,
        load_file=False,
        preserve=True,
    )

    try:
        _errors.reload()
    except JSONDeserializationError:
        # We can only recover from malformed json
        # If the default is malformed we do not catch it and just display the error
        cli.fail(
            f"errors.json at {config.data_dir() / 'errors.json'} is malformed JSON.\n"
            f"Will save copy and create new file."
        )
        # TODO: backup malformed file
        cli.animate_message_blocking(
            "errors.json is malformed. Restoring default database!", 3
        )
        _errors.restore_default(False)


def __default_file() -> None:
    """
    Revert to default errors file
    """
    global _errors
    cli.animate_message_blocking(
        "Writing default errors file to disk...",
        3,
        message_right="[CTRL-C to cancel]",
    )
    _errors.restore_default()
    cli.warn("Errors file reverted to default.")


def __errors_migrations() -> None:
    """
    Run error file migrations
    """
    global CURRENT_ERRORS_VERSION
    version = _errors.json["file"]["version"]
    try:
        version = int(version)
        match version:
            # Add future migrations here

            case _ if version == CURRENT_ERRORS_VERSION:
                cli.success(
                    f"Errors file version {version} is up to date.",
                    verbosity=logging.DEBUG,
                )
                return
            case _:
                cli.fail(
                    f"Errors file version {version} is unknown. Maybe too new?\n"
                    f"Will revert to default Errors file."
                )
                __default_file()
                return
    except ValueError:
        cli.fail(
            f"Errors file version is not an integer (got {version})\n"
            f"Will revert to default Errors file."
        )
        __default_file()
        return
    except KeyError:
        cli.fail(
            "Errors file.json is malformed, missing 'Errors file.version' key\n"
            "Will revert to default Errors file."
        )
        __default_file()
        return


def log_error(exception: Exception, context: str, fatal: bool) -> None:
    """
    Log an error to the errors database

    :param exception: Exception to log
    :param context: Context to log
    :param fatal: Whether the error was fatal for program execution
    """
    global _errors

    _errors.json["errors"].append(
        {
            "timestamp": int(time()),
            "exception_type": type(exception).__name__,
            "exception_message": str(exception),
            "context": context,
            "fatal": fatal,
        }
    )

    _errors.save()
