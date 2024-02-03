.. _pymemcache: https://pypi.python.org/pypi/pymemcache
.. _redis: https://pypi.python.org/pypi/redis
.. _github issue #41: https://github.com/alisaifee/flask-limiter/issues/41
.. _flask apps and ip spoofing: http://esd.io/blog/flask-apps-heroku-real-ip-spoofing.html

.. image:: _static/logo.png
    :target: /
    :width: 600px
    :align: center
    :class: logo

=============
Flask-Limiter
=============

.. currentmodule:: flask_limiter

.. toctree::
   :maxdepth: 2
   :hidden:

   strategies
   configuration
   recipes
   cli
   api
   development
   changelog
   misc


.. container:: badges

   .. image:: https://img.shields.io/github/last-commit/alisaifee/flask-limiter?logo=github&style=for-the-badge&labelColor=#282828
      :target: https://github.com/alisaifee/flask-limiter
      :class: header-badge
   .. image:: https://img.shields.io/github/actions/workflow/status/alisaifee/flask-limiter/main.yml?logo=github&style=for-the-badge&labelColor=#282828
      :target: https://github.com/alisaifee/flask-limiter/actions/workflows/main.yml
      :class: header-badge
   .. image:: https://img.shields.io/codecov/c/github/alisaifee/flask-limiter?logo=codecov&style=for-the-badge&labelColor=#282828
      :target: https://app.codecov.io/gh/alisaifee/flask-limiter
      :class: header-badge
   .. image:: https://img.shields.io/pypi/pyversions/flask-limiter?style=for-the-badge&logo=pypi
      :target: https://pypi.org/project/flask-limiter
      :class: header-badge

**Flask-Limiter** adds rate limiting to :class:`~flask.Flask` applications.

By adding the extension to your flask application, you can configure various
rate limits at different levels (e.g. application wide, per :class:`~flask.Blueprint`,
routes, resource etc).

**Flask-Limiter** can be configured to persist the rate limit state to many
commonly used storage backends via the :doc:`limits:index` library.


Let's get started!

Installation
============

**Flask-Limiter** can be installed via :program:`pip`.

.. code:: console

  $ pip install Flask-Limiter

To include extra dependencies for a specific storage backend you can add the
specific backend name via the ``extras`` notation. For example:

.. tab:: Redis

   .. code:: console

      $ pip install Flask-Limiter[redis]

.. tab:: Memcached

   .. code:: console

      $ pip install Flask-Limiter[memcached]

.. tab:: MongoDB

   .. code:: console

      $ pip install Flask-Limiter[mongodb]


Quick start
===========
A very basic setup can be achieved as follows:

.. literalinclude:: ../../examples/sample.py
   :language: py

The above Flask app will have the following rate limiting characteristics:

* Use an in-memory storage provided by :class:`limits.storage.MemoryStorage`.

  .. note:: This is only meant for testing/development and should be replaced with
     an appropriate storage of your choice before moving to production.
* Rate limiting by the ``remote_address`` of the request
* A default rate limit of 200 per day, and 50 per hour applied to all routes.
* The ``slow`` route having an explicit rate limit decorator will bypass the default
  rate limit and only allow 1 request per day.
* The ``medium`` route inherits the default limits and adds on a decorated limit
  of 1 request per second.
* The ``ping`` route will be exempt from any default rate limits.

  .. tip:: The built in flask static files routes are also exempt from rate limits.

Every time a request exceeds the rate limit, the view function will not get called and instead
a `429 <http://tools.ietf.org/html/rfc6585#section-4>`_ http error will be raised.

The extension adds a ``limiter`` subcommand to the :doc:`Flask CLI <flask:cli>` which can be used to inspect
the effective configuration and applied rate limits (See :ref:`cli:Command Line Interface` for more details).

Given the quick start example above:


.. code-block:: shell

   $ flask limiter config

.. program-output:: FLASK_APP=../../examples/sample.py:app flask limiter config
   :shell:

.. code-block:: shell

   $ flask limiter limits

.. program-output:: FLASK_APP=../../examples/sample.py:app flask limiter limits
   :shell:

The Flask-Limiter extension
---------------------------
The extension can be initialized with the :class:`flask.Flask` application
in the usual ways.

Using the constructor

   .. code-block:: python

      from flask_limiter import Limiter
      from flask_limiter.util import get_remote_address
      ....

      limiter = Limiter(get_remote_address, app=app)

Deferred app initialization using :meth:`~flask_limiter.Limiter.init_app`

   .. code-block:: python

      limiter = Limiter(get_remote_address)
      limiter.init_app(app)

At this point it might be a good idea to look at the configuration options
available in the extension in the :ref:`configuration:using flask config` section and the
:class:`flask_limiter.Limiter` class documentation.

-----------------------------
Configuring a storage backend
-----------------------------

The extension can be configured to use any storage supported by :pypi:`limits`.
Here are a few common examples:

.. tab:: Memcached

   Any additional parameters provided in :paramref:`~Limiter.storage_options`
   will be passed to the constructor of the memcached client
   (either :class:`~pymemcache.client.base.PooledClient` or :class:`~pymemcache.client.hash.HashClient`).
   For more details see :class:`~limits.storage.MemcachedStorage`.

   .. code-block:: python

      from flask_limiter import Limiter
      from flask_limiter.util import get_remote_address
      ....

      limiter = Limiter(
          get_remote_address,
          app=app,
          storage_uri="memcached://localhost:11211",
          storage_options={}
      )

.. tab:: Redis

   Any additional parameters provided in :paramref:`~Limiter.storage_options`
   will be passed to :meth:`redis.Redis.from_url` as keyword arguments.
   For more details see :class:`~limits.storage.RedisStorage`

   .. code-block:: python

      from flask_limiter import Limiter
      from flask_limiter.util import get_remote_address
      ....

      limiter = Limiter(
        get_remote_address,
        app=app,
        storage_uri="redis://localhost:6379",
        storage_options={"socket_connect_timeout": 30},
        strategy="fixed-window", # or "moving-window"
      )

.. tab:: Redis (reused connection pool)

   If you wish to reuse a :class:`redis.connection.ConnectionPool` instance
   you can pass that in :paramref:`~Limiter.storage_option`

   .. code-block:: python

      import redis
      from flask_limiter import Limiter
      from flask_limiter.util import get_remote_address
      ....

      pool = redis.connection.BlockingConnectionPool.from_url("redis://.....")
      limiter = Limiter(
        get_remote_address,
        app=app,
        storage_uri="redis://",
        storage_options={"connection_pool": pool},
        strategy="fixed-window", # or "moving-window"
      )

.. tab:: Redis Cluster

   Any additional parameters provided in :paramref:`~Limiter.storage_options`
   will be passed to :class:`~redis.cluster.RedisCluster` as keyword arguments.
   For more details see :class:`~limits.storage.RedisClusterStorage`

   .. code-block:: python

      from flask_limiter import Limiter
      from flask_limiter.util import get_remote_address
      ....

      limiter = Limiter(
        get_remote_address,
        app=app,
        storage_uri="redis+cluster://localhost:7000,localhost:7001,localhost:7002",
        storage_options={"socket_connect_timeout": 30},
        strategy="fixed-window", # or "moving-window"
      )

.. tab:: MongoDB

   .. code-block:: python

      from flask_limiter import Limiter
      from flask_limiter.util import get_remote_address
      ....

      limiter = Limiter(
        get_remote_address,
        app=app,
        storage_uri="mongodb://localhost:27017",
        strategy="fixed-window", # or "moving-window"
      )

The :paramref:`~Limiter.storage_uri` and :paramref:`~Limiter.storage_options` parameters
can also be provided by :ref:`configuration:using flask config` variables. The different
configuration options for each storage can be found in the :doc:`storage backend documentation for limits <limits:storage>`
as that is delegated to the :pypi:`limits` library.

.. _ratelimit-domain:

Rate Limit Domain
-----------------
Each :class:`~flask_limiter.Limiter` instance must be initialized with a
:paramref:`~Limiter.key_func` that returns the bucket in which each request
is put into when evaluating whether it is within the rate limit or not.

For simple setups a utility function is provided:
:func:`~flask_limiter.util.get_remote_address` which uses the
:attr:`~flask.Request.remote_addr` from :class:`flask.Request`.

Please refer to :ref:`deploy-behind-proxy` for an example.


Decorators to declare rate limits
=================================
Decorators made available as instance methods of the :class:`~flask_limiter.Limiter`
instance to be used with the :class:`flask.Flask` application.

.. _ratelimit-decorator-limit:

Route specific limits
---------------------

.. automethod:: Limiter.limit
   :noindex:

There are a few ways of using the :meth:`~flask_limiter.Limiter.limit` decorator
depending on your preference and use-case.

----------------
Single decorator
----------------

The limit string can be a single limit or a delimiter separated string

.. code-block:: python

   @app.route("....")
   @limiter.limit("100/day;10/hour;1/minute")
   def my_route()
     ...

-------------------
Multiple decorators
-------------------

The limit string can be a single limit or a delimiter separated string
or a combination of both.

.. code-block:: python

    @app.route("....")
    @limiter.limit("100/day")
    @limiter.limit("10/hour")
    @limiter.limit("1/minute")
    def my_route():
      ...

----------------------
Custom keying function
----------------------

By default rate limits are applied based on the key function that the :class:`~flask_limiter.Limiter` instance
was initialized with. You can implement your own function to retrieve the key to rate limit by
when decorating individual routes. Take a look at :ref:`keyfunc-customization` for some examples..

.. code-block:: python

   def my_key_func():
     ...

   @app.route("...")
   @limiter.limit("100/day", my_key_func)
   def my_route():
     ...

.. note:: The key function  is called from within a
    :doc:`flask request context <flask:reqcontext>`.

----------------------------------
Dynamically loaded limit string(s)
----------------------------------

There may be situations where the rate limits need to be retrieved from
sources external to the code (database, remote api, etc...). This can be
achieved by providing a callable to the decorator.


.. code-block:: python

   def rate_limit_from_config():
       return current_app.config.get("CUSTOM_LIMIT", "10/s")

   @app.route("...")
   @limiter.limit(rate_limit_from_config)
   def my_route():
       ...

.. warning:: The provided callable will be called for every request
    on the decorated route. For expensive retrievals, consider
    caching the response.


.. note:: The callable is called from within a
   :doc:`flask request context <flask:reqcontext>` during the
   `before_request` phase.


--------------------
Exemption conditions
--------------------

Each limit can be exempted when given conditions are fulfilled. These
conditions can be specified by supplying a callable as an
:attr:`exempt_when` argument when defining the limit.

.. code-block:: python

  @app.route("/expensive")
  @limiter.limit("100/day", exempt_when=lambda: current_user.is_admin)
  def expensive_route():
    ...

.. _ratelimit-decorator-shared-limit:

Reusable limits
---------------

For scenarios where a rate limit should be shared by multiple routes
(For example when you want to protect routes using the same resource
with an umbrella rate limit).

.. automethod:: Limiter.shared_limit
   :noindex:


------------------
Named shared limit
------------------

.. code-block:: python

  mysql_limit = limiter.shared_limit("100/hour", scope="mysql")

  @app.route("..")
  @mysql_limit
  def r1():
      ...

  @app.route("..")
  @mysql_limit
  def r2():
      ...


--------------------
Dynamic shared limit
--------------------

When a callable is passed as scope, the return value
of the function will be used as the scope. Note that the callable takes one argument: a string representing
the request endpoint.

.. code-block:: python

   def host_scope(endpoint_name):
       return request.host
   host_limit = limiter.shared_limit("100/hour", scope=host_scope)

   @app.route("..")
   @host_limit
   def r1():
       ...

   @app.route("..")
   @host_limit
   def r2():
       ...


.. _ratelimit-decorator-exempt:

Decorators for skipping rate limits
-----------------------------------

Registering exemptions from rate limits
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. automethod:: Limiter.exempt
   :noindex:

.. _ratelimit-decorator-request-filter:

Skipping a rate limit based on a request
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This decorator marks a function as a filter for requests that are going to be tested for rate limits. If any of the request filters return ``True`` no
rate limiting will be performed for that request. This mechanism can be used to
create custom white lists.

.. automethod:: Limiter.request_filter
   :noindex:

.. code-block:: python

   @limiter.request_filter
   def header_whitelist():
       return request.headers.get("X-Internal", "") == "true"

   @limiter.request_filter
   def ip_whitelist():
       return request.remote_addr == "127.0.0.1"

In the above example, any request that contains the header ``X-Internal: true``
or originates from localhost will not be rate limited.


For more complex use cases, refer to the :ref:`recipes:recipes` section.
