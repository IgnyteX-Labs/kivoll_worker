__version__: str
"""kivoll_worker version fetched from setuptools_scm 
or (if not available) set to '0+unknown'."""

try:
    # Prefer the file written by setuptools_scm at build/install time
    from .__about__ import __version__
except Exception:  # file not generated yet (e.g., fresh clone)
    try:
        # If the package is installed, ask importlib.metadata
        from importlib.metadata import version as _pkg_version

        __version__ = _pkg_version("kivoll_worker")
    except Exception:
        # Last resort for local source trees without SCM metadata
        __version__ = "0+unknown"


# We'll derive a short version by trimming any local/dev suffixes after the third dot.
def _short_version(ver: str) -> str:
    # Take first three numeric components (e.g., 1.2.3) if present.
    parts = ver.split(".")
    if len(parts) >= 2:
        return ".".join(parts[:3])
    return ver


__short_version__ = _short_version(__version__)

__all__ = ["__version__", __short_version__]
