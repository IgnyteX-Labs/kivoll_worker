"""
Kivoll worker top module
"""

try:
    from ._version import __version__
except ImportError:
    try:
        from importlib.metadata import PackageNotFoundError
        from importlib.metadata import version as _v

        __version__ = _v("kivoll_worker")
    except PackageNotFoundError:
        __version__ = "0+unknown"


# We'll derive a short version by trimming any local/dev suffixes after the third dot.
def _short_version(ver: str) -> str:
    # Take the first three numeric components (e.g., 1.2.3) if present.
    parts = ver.split(".")
    if len(parts) >= 2:
        return ".".join(parts[:3])
    return ver


__short_version__ = _short_version(__version__)

__all__ = ["__version__", __short_version__]
