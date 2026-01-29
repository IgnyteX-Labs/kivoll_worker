Welcome to the kivoll_worker documentation!
===============================================

kivoll_worker is a set of tools to automate occupancy data collection.

Currently it tracks the following tings:
- Scrapes occupancy data from Kletterzentrum Innsbruck
- Scrapes weather forecast data from Open-Meteo

Planned:
- Occupancy for other places

.. warning::
    Beware that the project is not affiliated with Kletterzentrum Innsbruck.
    Use at your own risk.
    The web scraper scrapes the html and will eventually break
    when the website structure changes.


Installation & Usage:
---------------------
kivoll_worker does not release as a PyPI package (yet?) and maybe never will.

It is highly recommended to run the entire ``kivoll`` project with the
instructions from ``kivoll_infra`` repository.

To install the latest version directly from the repository, run:
.. code-block:: bash

    git clone https://ignytex-labs/kivoll_worker.git
    cd kivoll_worker
    uv sync

This allows you to access these command line tools:

.. code-block:: bash

    kivoll-scrape --help
    kivoll-schedule --help

Further reading
=================
This documentation only provides information relevant to ``kivoll_worker``.

For information on ``kivoll`` as a whole, please refer to the
``kivoll_infra`` documentation at: not yet available =)

Contents
========
Information about configuration, development

.. toctree::
    :maxdepth: 2
    :caption: Contents

    development
    kletterzentrum
    weather

.. toctree::
    :maxdepth: 2
    :caption: API Reference

    api/index


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`