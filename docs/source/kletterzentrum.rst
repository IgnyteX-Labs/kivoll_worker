Kletterzentrum module
======================

The kletterzentrum module provides functionality to scrape occupancy data
from the Kletterzentrum Innsbruck website.

The module config lives in ``config.json`` under the ``modules/kletterzentrum`` key:

.. code-block:: json

    "kletterzentrum": {
      "user_agent": "kivoll/%s (scraper) at gh.io/ignytex-labs/kivoll_worker",
      "url": "https://www.kletterzentrum-innsbruck.at/auslastung/"
    }