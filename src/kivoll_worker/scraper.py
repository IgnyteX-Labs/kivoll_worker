from cliasi import Cliasi

from kivoll_worker.common.arguments import parse_scrape_args
from kivoll_worker.scrape.kletterzentrum import kletterzentrum
from kivoll_worker.scrape.weather import weather
from kivoll_worker.storage import init_db


def main() -> int:
    """
    Entry point for the `kivoll_worker-scrape` CLI command.
    :return: int status code
    """
    args = parse_scrape_args()
    cli = Cliasi(
        "scraper",
    )

    init_db()

    failed = 0
    cli.info("Scraping kletterzentrum", message_right="[1/2]")
    failed += 0 if kletterzentrum(dry_run=args.dry_run) else 0
    cli.info("Scraping weather", message_right="[2/2]")
    failed += 0 if weather() else 0
    cli.success("Scraping complete.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
