Deploy project
===============

To deploy the project, fill in the passwords under
``deploy/.env.admin.example`` and ``deploy/.env.admin.example``
and rename the files without the ``.example``

.. note::
    The .env files will be used to fill in data in the ``.sql`` files under ``initdb``

Then deploy with docker
.. code-block:: shell

    docker compose -f deploy/docker-compose.yml up -d