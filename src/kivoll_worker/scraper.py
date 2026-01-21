from argparse import Namespace
from collections.abc import Callable
from datetime import datetime, time

from cliasi import Cliasi

from kivoll_worker.common.arguments import parse_scrape_args
from kivoll_worker.common.config import get_tz
from kivoll_worker.common.failure import log_error
from kivoll_worker.scrape.kletterzentrum import kletterzentrum
from kivoll_worker.scrape.weather import weather
from kivoll_worker.storage import init_db

SCRAPE_TARGETS: dict[
    str, dict[str, tuple[time, time] | Callable[[Namespace], bool] | str]
] = {
    "weather": {
        "run": lambda _: weather(),
        "interval": "0",
    },
    "kletterzentrum": {
        "run": lambda args: kletterzentrum(args),
        "interval": "*/5",
        "open": (time(9, 0), time(22, 0)),
    },
}


def _parse_time_of_day(raw: str, cli: Cliasi) -> time:
    try:
        hours, minutes = raw.split(":", maxsplit=1)
        return time(hour=int(hours), minute=int(minutes))
    except Exception as exc:  # noqa: BLE001
        cli.fail("Invalid time for --time-of-day, expected HH:MM")
        log_error(exc, "scraper:time-of-day:parse", False)
        raise


def _reference_time(time_of_day: str | None, cli: Cliasi) -> time:
    timezone = get_tz(cli)
    if time_of_day:
        ref = _parse_time_of_day(time_of_day, cli)
        cli.log(f"Using provided time of day {ref.strftime('%H:%M')} ({timezone})")
        return ref
    now = datetime.now(timezone).time()
    cli.log(f"Using current time {now.strftime('%H:%M')} in configured timezone")
    return now


def _is_open(
    at: time,
    target_info: dict[str, tuple[time, time] | Callable[[Namespace], bool] | str],
) -> bool:
    if "open" in target_info and isinstance(target_info["open"], tuple):
        start, end = target_info["open"]
        return start <= at < end
    return True


def _open_targets(at: time) -> list[str]:
    return [
        name for name in SCRAPE_TARGETS.keys() if _is_open(at, SCRAPE_TARGETS[name])
    ]


def _resolve_targets(raw_targets: str | None, at: time, cli: Cliasi) -> list[str]:
    if raw_targets is None:
        cli.log("No explicit targets supplied; selecting currently open targets")
        return _open_targets(at)

    selections: list[str] = []
    tokens = [
        token.strip().lower() for token in raw_targets.split(",") if token.strip()
    ]
    for token in tokens:
        if token == "all":
            for name in SCRAPE_TARGETS:
                if name not in selections:
                    selections.append(name)
            continue
        if token in SCRAPE_TARGETS and token not in selections:
            selections.append(token)
            continue
        cli.warn(f"Unknown target '{token}' will be ignored")
        log_error(
            ValueError(f"Unknown scrape target '{token}'"),
            "scraper:targets:unknown",
            False,
        )

    if not selections:
        cli.warn("No valid targets requested; nothing to do.")
    return selections


def main() -> int:
    args = parse_scrape_args()
    cli = Cliasi("scraper")

    if args.list_targets:
        text = "Listing available targets:"
        for name, info in SCRAPE_TARGETS.items():
            text += f"\n- {name}: {info.get('description', '')}"
        cli.info(text)
        return 0

    init_db()

    try:
        ref_time = _reference_time(args.time_of_day, cli)
    except Exception as e:
        log_error(e, "scraper:time-of-day:resolve", False)
        cli.fail("Could not resolve time of day")
        return 1

    targets = _resolve_targets(args.targets, ref_time, cli)
    if not targets:
        cli.info("No targets to scrape at this time.")
        return 1

    failed = 0
    total = len(targets)
    for idx, target in enumerate(targets, start=1):
        if (
            "run" in SCRAPE_TARGETS[target]
            and (runner := SCRAPE_TARGETS[target]["run"])
            and callable(runner)
        ):
            cli.info(f"Scraping {target}", message_right=f"[{idx}/{total}]")
            try:
                success = runner(args)
            except Exception as exc:
                log_error(exc, f"scraper:run:{target}", False)
                cli.fail(
                    f"{target} scrape raised an exception: {exc}",
                    messages_stay_in_one_line=False,
                )
                success = False
            if not success:
                failed += 1

    if failed:
        cli.warn(
            f"{failed} target(s) failed, {total - failed} succeeded.",
            message_right=f"[{total}/{total}]",
        )
        return 1

    cli.success("Scraping successful.", message_right=f"[{total}/{total}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
