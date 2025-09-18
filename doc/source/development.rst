Development
===========

The source is available on `Github <https://github.com/alisaifee/flask-limiter>`_

To get started

.. code:: console

   $ git clone git://github.com/alisaifee/flask-limiter.git
   $ cd flask-limiter
   $ uv sync --dev

Tests
-----
Since some of the tests rely on having a redis & memcached instance available,
you will need a working docker installation to run all the tests.

.. code:: console

   $ uv run pytest


Running the tests will automatically invoke :program:`docker-compose` with the following config (:githubsrc:`docker-compose.yml`)

.. literalinclude:: ../../docker-compose.yml
