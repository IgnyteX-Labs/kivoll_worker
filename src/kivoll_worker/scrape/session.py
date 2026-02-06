from datetime import datetime, timedelta
from typing import Any

import niquests
import requests_cache
from niquests.adapters import HTTPAdapter

TOTAL_RETRIES = 3
STATUS_FORCELIST = [429, 500, 502, 503, 504]


class CachedSession(requests_cache.session.CacheMixin, niquests.Session):  # type: ignore[misc]
    """
    A session that combines niquests retries and requests_cache for caching and retries.
    """

    def __init__(self, cache_name: str = ".cache", **kwargs: Any) -> None:
        """Initialize the CachedSession with cache_name and optional kwargs."""
        super().__init__(cache_name, **kwargs)


def create_cached_scrape_session(
    cache_expire_after: None | int | float | str | datetime | timedelta,
    cache_name: str = ".cache",
) -> CachedSession:
    """
    Create a CachedSession with cache expiration time and retries configured.
    :param cache_expire_after: The expiration time for the cache.
    :param cache_name: The cache name/path to use (default: ".cache").
    :return: A CachedSession instance with retries configured.
    """
    session = CachedSession(cache_name, expire_after=cache_expire_after)
    set_reties_property(session)
    return session


def set_reties_property(session: niquests.Session | CachedSession) -> None:
    """
    Set the retries property on ScrapeSession to return the niquests.RetryConfiguration.

    :param session: The session to set the retries property on.
    """

    # Add to config but when config has been reworked.
    # I dont want config check code here...

    retries = niquests.RetryConfiguration(
        total=TOTAL_RETRIES,
        # No exponential backoff (user requested fixed-number retries)
        backoff_factor=0,
        # Retry on common transient server/client-slowdown statuses
        status_forcelist=STATUS_FORCELIST,
        # We only run GETS as of right now but why not
        allowed_methods=["GET", "HEAD", "OPTIONS"],
        # Respect Retry-After header when present
        respect_retry_after_header=True,
    )

    # Set the property for inspection/testing
    session.retries = retries

    # Mount adapters with retry configuration for both http and https
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)


def create_scrape_session() -> niquests.Session:
    """
    Create a default niquests Session with retries configured.
    :return: A niquests Session instance with retries configured.
    """
    session = niquests.Session()
    set_reties_property(session)
    return session
