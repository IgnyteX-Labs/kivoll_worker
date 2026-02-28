Set up development environment
===============================

This project is a subproject of the kivoll project and requires a database to run.

Minimal set up
----------------
If you only plan on running kivoll_worker locally on your machine, you will need to
have a running kivoll_db instance. In order to do that, you will need docker installed.

Install dependencies
~~~~~~~~~~~~~~~~~~~~~

Install dependencies with ``uv``

.. code-block:: bash

    uv sync

.. deprecated:: 0.1.1
    SQLite support - you will need the kivoll_db container. (See below)


Set up environment variables
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Then, set up environment variables. You can copy the provided example file
under ``.env.example`` and adjust it to your needs.

.. code-block:: bash

    cp .env.example .env
    # Edit .env as needed

Running kivoll_db
~~~~~~~~~~~~~~~~~~~~~
Other parts of the kivoll project, such as the API server also require a running
the kivoll_db.

The database you are about to start will be shared across all projects.

To start the database run

.. code-block:: bash

    make db-up

This will start a PostgresSQL database on port 5432
with the default credentials specified in ``.env`` (the one you copied and modified)

.. important::
    The database requires a few environment variables to be set in order to initialize.
    The database might have updated, so look for new environment variables
    in the ``.env.example`` file and add them to your ``.env`` file.

Running kivoll
----------------

Run with environment variables set
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
kivoll_worker requires certain environment variables to be set
in order to connect to the DB.

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

.. important::
    The code will be mounted inside the container, so any changes you make to the code
    will be reflected inside the container instantly.

.. warning::
    The local.Dockerfile will sync the dependencies in a build step so if you add
    dependencies, you will need to rebuild the image to add them to the cache.

If you want to run the container in detached mode, you can use

.. code-block:: bash

    make docker-headless

Docker configuration
---------------------

Docker files
~~~~~~~~~~~~~~
* The local.Dockerfile is intended for local development and testing.
  It needs the code to be mounted inside the container to be able to
  reflect live changes instantly.

* Dockerfile is intended for production use
  and is used in the CI/CD pipeline to build the kivoll_worker image
  and push it to GitHub Container Registry.

Docker stages
~~~~~~~~~~~~~~~
1. Both Dockerfiles fetch the project dependencies into a cache. (``deps`` stage)
2. The Dockerfile then builds a wheel. (``builder`` stage)
3. In runtime, both containers copy the dependency stage cache and install the project.

Healthcheck
~~~~~~~~~~~~~~~
Both Dockerfiles include a healthcheck.
``kivoll-schedule`` runs a small HTTP server which can be
checked using the ``kivoll-healthcheck`` command.

Running the healthcheck command will check if
``kivoll-schedule`` is running and healthy.

.. code-block:: bash

    kivoll-healthcheck

This command returns 0 if the ``kivoll-schedule`` is healthy and running,
and a non-zero code otherwise.


Deploy to ghcr.io
---------------------
The package will be automatically built and pushed to GitHub Container Registry
with the workflows/deploy.yml github action.
