# kivoll_worker

![GitHub issues](https://img.shields.io/github/issues/IgnyteX-Labs/kivoll_worker)
![Build status](https://img.shields.io/github/actions/workflow/status/ignytex-labs/kivoll_worker/test.yml)
![codecov](https://img.shields.io/codecov/c/github/ignytex-labs/kivoll_worker)

kivoll_worker is a set of tools to automate occupancy data collection.

It is a part of the overall kivoll project (see [kivoll_infra](https://github.com/Ignytex-Labs/kivoll_infra) for more information).

## Features
- Scrapes occupancy data from Kletterzentrum Innsbruck
- Scrapes weather forecast data from Open-Meteo

### Planned Features
- Occupancy tracking for other places

## Warning
This project is not affiliated with Kletterzentrum Innsbruck. Use at your own risk. The web scraper relies on the current HTML structure of the website and may break if the structure changes.

## Usage as container
The ``kivoll_worker`` container requires access to a PostgreSQL database

### Environment Variables
- `DB_HOST`: The database host (default: `localhost:5432`)
- `DB_DRIVER`: The database driver (default: `postgresql`)
- `WORKER_APP_PASSWORD`: Password for the worker application (``rw``)
- `WORKER_MIGRATOR_PASSWORD`: Username for the worker migrator (``DDL``)
- `SCHEDULER_DB_PASSWORD`: Username for the scheduler (``DDL``)

## Installation & Usage
kivoll_worker is not available as a PyPI package. It is recommended to run the entire `kivoll` project using the instructions from the `kivoll_infra` repository.

To install the latest version directly from the repository, run:

```bash
git clone https://ignytex-labs/kivoll_worker.git
cd kivoll_worker
uv sync
```

This will provide access to the following command-line tools:

```bash
kivoll-scrape --help
kivoll-schedule --help
```

## Documentation
For more information, visit the [kivoll_worker documentation](https://kivoll-worker.readthedocs.io).

For details about the `kivoll` project as a whole, refer to the `kivoll_infra` documentation (link not yet available).
