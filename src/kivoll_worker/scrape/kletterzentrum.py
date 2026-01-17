"""Fetch and parse occupancy (Auslastung) data from the Kletterzentrum website.

This module contains the parsing logic and a small CLI entrypoint. Prefer
importing `get_auslastung` for programmatic usage.
"""

import logging
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from cliasi import Cliasi
from requests import HTTPError

import kivoll_worker.storage

from .. import __short_version__
from ..common import config
from ..common.failure import log_error

cli: Cliasi = Cliasi("uninitialized")


@dataclass
class KletterzentrumOccupancyData:
    """Dataclass describing the occupancy data for Kletterzentrum Innsbruck"""

    overall: int | None = None
    seil: int | None = None
    boulder: int | None = None
    open_sectors: int | None = None
    total_sectors: int | None = None


def _cache_html(html: str) -> Path:
    """
    Cache the given HTML to the configured data directory
    :param html: HTML content as string
    """
    p = config.data_dir() / "last_request.html"
    p.write_text(html, encoding="utf-8")
    return p


def _load_cached_html() -> str:
    """
    Get the cached HTML from data_dir()/last_request.html
    :return: HTML content as string
    :raises FileNotFoundError: if the file does not exist
    """
    p = config.data_dir() / "last_request.html"
    try:
        return p.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        log_error(e, "kletterzentrum:load_cached_html", False)
        raise FileNotFoundError(
            f"No cached HTML file found at {p}!\n"
            f" Please run without --dry-run to fetch live data first."
        ) from e


def _parse_html(html: str) -> KletterzentrumOccupancyData:
    """
    Extract occupancy data from the given HTML.

    :param html: HTML content as string
    :return: ~kivoll_worker.scrape.get_occupancy.OccupancyData object
    """
    soup = BeautifulSoup(html, "html.parser")

    cli.log("Starting parsing of Kletterzentrum occupancy HTML")
    data = KletterzentrumOccupancyData()

    cli.log("Parsing overall")
    try:
        overall_val = None
        h2_candidates = soup.select("h2.x-text-content-text-primary") or soup.find_all(
            "h2"
        )
        for h2 in h2_candidates:
            txt = (h2.get_text(strip=True) or "").strip()
            m = re.search(r"(\d{1,3})", txt)
            if m:
                try:
                    overall_val = int(m.group(1))
                    break
                except ValueError:
                    pass
        data.overall = overall_val
        cli.success("Parsed overall occupation", verbosity=logging.DEBUG)
    except Exception as e:
        log_error(e, "kletterzentrum:parse:overall", False)
        cli.warn(f"Error parsing overall occupation: {e}")

    cli.log("Parsing section occupations (seil and boulder)")
    try:
        for container in soup.select(".bar-container"):
            label_el = container.select_one("span.label")
            perc_el = container.select_one("div.bar[data-percentage]")
            if not label_el or not perc_el:
                continue
            label = label_el.get_text(strip=True).lower()
            raw_perc = perc_el.get("data-percentage")
            if isinstance(raw_perc, list):
                raw_perc = raw_perc[0] if raw_perc else None
            if raw_perc is None:
                continue
            try:
                perc = int(str(raw_perc).strip())
            except Exception as e:
                log_error(e, "kletterzentrum:parse:sections:percentage", False)
                continue
            if "seil" in label:
                data.seil = perc
            elif "boulder" in label:
                data.boulder = perc
    except Exception as e:
        log_error(e, "kletterzentrum:parse:sections", False)
        cli.warn(f"Error parsing section occupations: {e}")

    # Fallback: look for inline CSS height percentages
    if data.seil is None or data.boulder is None:
        cli.log("Section occupancy not found using html, trying css data")
        try:
            css_matches = re.findall(r"height:\s*(\d{1,3})%", html)
            ints = []
            for m in css_matches:
                try:
                    ints.append(int(m))
                except Exception:
                    pass
            if data.seil is None and len(ints) >= 1:
                data.seil = ints[0]
            if data.boulder is None and len(ints) >= 2:
                data.boulder = ints[1]
        except Exception as e:
            log_error(e, "kletterzentrum:parse:css_fallbacks", False)
            cli.warn(f"Error parsing css fallbacks: {e}")
    cli.success("Parsed section occupancy", verbosity=logging.DEBUG)

    cli.log("Parsing open sectors")
    try:
        title = None
        for h in soup.find_all(["h3", "h2"]):
            if "offene sektoren" in (h.get_text(strip=True) or "").lower():
                title = h
                break
        open_val = None
        total_val = None
        if title is not None:
            first_span = title.find_next("span", class_="first")
            second_span = title.find_next("span", class_="second")
            if first_span is not None:
                m = re.search(r"\d+", first_span.get_text(strip=True) or "")
                if m:
                    try:
                        open_val = int(m.group(0))
                    except Exception:
                        pass
            if second_span is not None:
                m = re.search(r"\d+", second_span.get_text(strip=True) or "")
                if m:
                    try:
                        total_val = int(m.group(0))
                    except Exception:
                        pass
        data.open_sectors = open_val
        data.total_sectors = total_val
        cli.success("Parsed open sectors", verbosity=logging.DEBUG)
    except Exception as e:
        log_error(e, "kletterzentrum:parse:open_sectors", False)
        cli.fail(
            "Could not parse open sectors",
            verbosity=logging.DEBUG,
            messages_stay_in_one_line=False,
        )

    cli.success("Parsing successful", verbosity=logging.DEBUG)
    cli.log(
        f"Parsed values: overall={data.overall}%, seil={data.seil}%, "
        f"boulder={data.boulder}%, open_sectors={data.open_sectors}, "
        f"total_sectors={data.total_sectors}",
        verbosity=logging.DEBUG,
    )
    return data


def kletterzentrum(dry_run: bool) -> bool:
    """
    Fetch occupancy data from the Kletterzentrum Innsbruck website.

    :param dry_run:
        If True, load HTML from a saved file instead of making a network request.
        If no file is available, will throw error
    :return bool indicating success
    """
    global cli
    cli = Cliasi("KI")
    if dry_run:
        cli.warn(
            "Using cached HTML (DRY RUN). Will not save data to database",
            messages_stay_in_one_line=False,
        )
        html = _load_cached_html()
        cli.success("File read", logging.DEBUG)
    else:
        ua = (
            config.config()
            .get("modules", {})
            .get("web", {})
            .get("user_agent", f"kivoll_worker-get-occupancy/{__short_version__}")
        )
        ua = f"kivoll_worker-get-occupancy/{__short_version__}"
        if (
            "modules" in config.config()
            and "web" in config.config()["modules"]
            and "user_agent" in config.config()["modules"]["web"]
        ):
            ua = config.config()["modules"]["web"]["user_agent"]
        else:
            cli.warn("Could not retrieve user agent to use (malformed config)")
            log_error(
                ValueError("Could not retrieve user agent to use (malformed config)"),
                "kletterzentrum:fetch:ua_error",
                False,
            )

        headers = {"User-Agent": (ua % __short_version__) if "%s" in ua else ua}

        if (
            "modules" in config.config()
            and "web" in config.config()["modules"]
            and "url" in config.config()["modules"]["web"]
        ):
            url = config.config()["modules"]["web"]["url"]
        else:
            cli.fail("Could not retrieve url to use (malformed config)")
            log_error(
                ValueError("Could not retrieve url to use (malformed config)"),
                "kletterzentrum:fetch:url_error",
                False,
            )
            return False

        task = cli.animate_message_download_non_blocking(
            f"Fetching KI occupancy at {url}", verbosity=logging.DEBUG
        )
        try:
            response = requests.get(url, headers=headers)
            task.update("Fetch complete, checking response") if task else None
            response.raise_for_status()
        except HTTPError as e:
            task.stop() if task else None
            cli.fail(
                "Could not fetch data for Kletterzentrum!",
                messages_stay_in_one_line=False,
            )
            log_error(e, "kletterzentrum:fetch:http_error", False)
            return False

        task.stop() if task else None
        cli.success("Kletterzentrum website fetched", logging.DEBUG)
        cli.info("Writing html to data/last_request.html")
        html = response.text
        try:
            _cache_html(html)
        except Exception as e:
            cli.warn("Could not write last_request.html")
            log_error(e, "kletterzentrum:cache_html", False)

    # Parse values
    parsed = _parse_html(html)
    # Storing values in the database
    if not parsed:
        return False

    if dry_run:
        return True
    cli.log("Connecting to database")
    database = kivoll_worker.storage.connect()
    success = True
    try:
        cli.log("Writing kletterzentrum values")
        database.execute(
            """
            INSERT INTO kletterzentrum_data
            (timestamp, overall, seil, boulder, open_sectors, total_sectors)
            VALUES (strftime('%s','now'), ?, ?, ?, ?, ?)
            """,
            (
                parsed.overall,
                parsed.seil,
                parsed.boulder,
                parsed.open_sectors,
                parsed.total_sectors,
            ),
        )
        cli.log("Committing changes")
        database.commit()
        cli.success("Kletterzentrum data written to database", logging.DEBUG)
    except sqlite3.Error as e:
        success = False
        log_error(e, "kletterzentrum:dbstore:sqlite", False)
        cli.fail(
            f"Could not store kletterzentrum data to database!\nError: {e}",
            messages_stay_in_one_line=False,
        )
        database.rollback()
    except Exception as e:
        success = False
        log_error(e, "kletterzentrum:dbstore:unknown", False)
        cli.fail(
            f"An unexpected error occurred while storing kletterzentrum data!\n"
            f"Error: {e}",
            messages_stay_in_one_line=False,
        )
        database.rollback()
    finally:
        database.close()

    return success
