API Reference
=============

.. toctree::
   :maxdepth: 1
   :caption: Subpackages

   common
   scrape
   storage

CLI entry points
====================

The main kivoll_worker CLI entry points all live in the top level
``kivoll_worker`` module and are documented below

Scheduler
----------

.. note::
    Entry point: ``kivoll-schedule``

.. automodule:: kivoll_worker.scheduler
   :members:
   :undoc-members:
   :show-inheritance:

Scraper
--------

.. note::
    Entry point: ``kivoll-scrape``

.. automodule:: kivoll_worker.scraper
   :members:
   :undoc-members:
   :show-inheritance:

Healthcheck Client
-----------------------

.. note::
    Entry point: ``kivoll-healthcheck``

.. automodule:: kivoll_worker.healthcheck_client
   :members:
   :undoc-members:
   :show-inheritance: