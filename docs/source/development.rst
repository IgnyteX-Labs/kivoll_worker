Set up development environment
===============================

This project is a subproject of the kivoll project and requires a database to run.

Minimal set up
----------------
If you only plan on running kivoll_worker locally on your machine, it will automatically
fall back to SQLite as a database backend. In this case, you only need to install the required
dependencies and run the application.

.. code-block:: bash

    uv sync

.. warning::
    SQLite support may be dropped in the future.

Full local development environment
-----------------------------------
To set up a full local development environment, you will need to install docker and docker-compose.

First up, set up environment variables. You can copy the provided example file
under ``deploy/.env.example`` and adjust it to your needs.

.. code-block:: bash

    cp .env.example .env
    # Edit .env as needed

Local database
~~~~~~~~~~~~~~~~
Other parts of the kivoll project, such as the API server and the web frontend, also require a running
a database. If you want all projects to access the same database, you can use the provided
docker-compose configuration in ``deploy/db/docker-compose.yml``.

To start the database run

.. code-block:: bash

    cd deploy/db
    make up

This will start a PostgresSQL database on port 5432 with the default credentials specified in ``.env``

Run with environment variables set
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
kivoll_worker requires certain environment variables to be set in order to not default to SQLite.

To set these variables, use the Makefile.

.. code-block:: bash

    make env

.. tip::
    If you are already using the docker database, consider running the application inside a docker container as well.

Run in docker container
~~~~~~~~~~~~~~~~~~~~~~~~~~~
To run the application inside a docker container, you can use the provided Dockerfile and Makefile.

.. code-block:: bash

    make docker-build
    make docker-run

This will build the docker image and run the container with the environment variables set from ``.env``.