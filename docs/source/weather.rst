Supported weather variables
==============================
Weather data is scraped with the  ``openmeteo_requests`` module.

You can configure weather variables to track in the ``config.json`` file
under the ``modules/weather`` key.

.. code-block:: json

    "weather": {
      "url": "https://api.open-meteo.com/v1/forecast",
      "locations": {
        "kletterzentrum": {
          "latitude": 47.27681,
          "longitude": 11.413439,
          "enabled": true
        }
      },
      "parameters": {
        "daily": [
          "..."
        ],
        "hourly": [
          "..."
        ],
        "current": [
          "..."
        ],
        "timezone": "Europe/Berlin",
        "forecast_days": 1
      }
    },

Supported weather parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The current version of ``kivoll_worker`` (|version|)
supports the following weather variables:

.. weather-parameters::
