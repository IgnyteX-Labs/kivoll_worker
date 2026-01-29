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
    SQLite support will be dropped in the near future.

Full local development environment
-----------------------------------
To set up a full local development environment, you will need to install docker.

First up, set up environment variables. You can copy the provided example file
under ``.env.example`` and adjust it to your needs.

.. code-block:: bash

    cp .env.example .env
    # Edit .env as needed

Local database
~~~~~~~~~~~~~~~~
Other parts of the kivoll project, such as the API server also require a running
a database. If you want all projects to access the same database, you can use the provided
database which can be started via the Makefile

To start the database run

.. code-block:: bash

    make db-up

This will start a PostgresSQL database on port 5432 with the default credentials specified in ``.env``

.. warning::
    Make sure that all env variables are present (see the most recent commits), otherwise
    the database might not initialize correctly.

Run with environment variables set
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
kivoll_worker requires certain environment variables to be set in order to connect to the DB.

To set these variables, use the Makefile.

.. code-block:: bash

    make env

.. tip::
    If you are already using the docker database,
    consider running kivoll_worker inside a docker container as well.

Run in docker container
~~~~~~~~~~~~~~~~~~~~~~~~~~~
To run the application inside a docker container,
you can use the provided local.Dockerfile and Makefile.

.. code-block:: bash

    make docker-build
    make docker-shell

This will build the docker image and run the container with the
environment variables set from ``.env``.

If you want to run the container in detached mode, you can use

.. code-block:: bash

    make docker-headless


Deploy to ghcr.io
---------------------
The package will be automatically built and pushed to GitHub Container Registry
with a github action.

The workflows to do that locally do not exist