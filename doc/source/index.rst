.. _pymemcache: https://pypi.python.org/pypi/pymemcache
.. _redis: https://pypi.python.org/pypi/redis

*************
Flask-Limiter
*************
.. currentmodule:: flask_limiter

Usage
=====

Quick start
-----------
.. code-block:: python

   from flask import Flask
   from flask_limiter import Limiter

   app = Flask(__name__)
   limiter = Limiter(app, global_limits=["200 per day", "50 per hour"])

   @app.route("/slow")
   @limiter.limit("1 per day")
   def slow():
       return "24"

   @app.route("/fast")
   def fast():
       return "42"

   @app.route("/ping")
   @limiter.exempt
   def ping():
       return "PONG"


The above Flask app will have the following rate limiting characteristics:

* A global rate limit of 200 per day, and 50 per hour applied to all routes.
* The ``slow`` route having an explicit rate limit decorator will bypass the global
  rate limit and only allow 1 request per day.
* The ``ping`` route will be exempt from any global rate limits.

.. note:: The built in flask static files routes are also exempt from rate limits.

Every time a request exceeds the rate limit, the view function will not get called and instead
a `429 <http://tools.ietf.org/html/rfc6585#section-4>`_ http error will be raised.

The Flask-Limiter extension
---------------------------
The extension can be initialized with the :class:`flask.Flask` application
in the usual ways.

Using the constructor

   .. code-block:: python

      from flask_limiter import Limiter
      ....

      limiter = Limiter(app)

Using ``init_app``

    .. code-block:: python

        limiter = Limiter()
        limiter.init_app(app)


Decorators
----------
Each route can be decorated to override the global rate limits set in the extension.
The two decorators made available as instance methods of the :class:`Limiter`
instance are

:meth:`Limiter.limit`
  There are a few ways of using this decorator depending on your preference and use-case.

  Single decorator
    The limit string can be a single limit or a delimiter separated string

      .. code-block:: python

         @app.route("....")
         @limiter.limit("100/day;10/hour;1/minute")
         def my_route()
           ...

  Multiple decorators
    The limit string can be a single limit or a delimiter separated string
    or a combination of both.

        .. code-block:: python

           @app.route("....")
           @limiter.limit("100/day")
           @limiter.limit("10/hour")
           @limiter.limit("1/minute")
           def my_route():
             ...

  Custom keying function
    By default rate limits are applied on per remote address basis. You can implement
    your own function to retrieve the key to rate limit by. Take a look at :ref:`keyfunc-customization`
    for some examples..

        .. code-block:: python

            def my_key_func():
              ...

            @app.route("...")
            @limiter.limit("100/day", my_key_func)
            def my_route():
              ...

        .. note:: The key function  is called from within a
           :ref:`flask request context <flask:request-context>`.

  Dynamically loaded limit string(s)
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

        .. danger:: The provided callable will be called for every request
           on the decorated route. For expensive retrievals, consider
           caching the response.
        .. note:: The callable is called from within a
           :ref:`flask request context <flask:request-context>`.

:meth:`Limiter.exempt`
  This decorator simply marks a route as being exempt from any rate limits.


Configuration
=============
The following flask configuration values are honored by
:class:`Limiter`

.. tabularcolumns:: |p{6.5cm}|p{8.5cm}|

============================== ================================================
``RATELIMIT_GLOBAL``           A comma (or some other delimiter) separated string
                               that will be used to apply a global limit on all
                               routes. If not provided, the global limits can be
                               passed to the :class:`Limiter` constructor
                               as well (the values passed to the constructor take precedence
                               over those in the config). :ref:`ratelimit-string` for details.
``RATELIMIT_STORE_URL``        One of ``memory://`` or ``redis://host:port``
                               or ``memcached://host:port``. Using the redis storage
                               requires the installation of the `redis`_ package
                               while memcached relies on the `pymemcache`_ package.
``RATELIMIT_STRATEGY``         The rate limiting strategy to use.  :ref:`ratelimit-strategy`
                               for details.
``RATELIMIT_ENABLED``          Overall killswitch for ratelimits. Defaults to ``True``
============================== ================================================


.. _ratelimit-string:

Rate limit string notation
==========================

Rate limits are specified as strings following the format:

    [count] [per|/] [n (optional)] [second|minute|hour|day|month|year]

You can combine multiple rate limits by separating them with a delimiter of your
choice.

Examples
--------

* 10 per hour
* 10/hour
* 10/hour;100/day;2000 per year
* 100/day, 500/7days

.. warning:: If rate limit strings that are provided to the :meth:`Limiter.limit`
   decorator are malformed and can't be parsed the decorated route will fall back
   to the global rate limit(s) and an ``ERROR`` log message will be emitted. Refer
   to :ref:`logging` for more details on capturing this information. Malformed
   global rate limit strings will howere raise an exception as they are evaluated
   early enough to not cause disruption to a running application.


.. _ratelimit-strategy:

Rate limiting strategies
========================
Flask-Limiter comes with three different rate limiting strategies built-in. Pick
the one that works for your use-case by specifying it in your flask config as
``RATELIMIT_STRATEGY`` (one of ``fixed-window``, ``fixed-window-elastic-expiry``,
or ``moving-window``). The default configuration is ``fixed-window``.


Fixed Window
------------
This is the most memory efficient strategy to use as it maintains one counter
per resource and rate limit. It does however have its drawbacks as it allows
bursts within each window - thus allowing an 'attacker' to by-pass the limits.
The effects of these burts can be partially circumvented by enforcing multiple
granularities of windows per resource.

For example, if you specify a ``100/minute`` rate limit on a route, this strategy will
allow 100 hits in the last second of one window and a 100 more in the first
second of the next window. To ensure that such bursts are managed, you could add a second rate limit
of ``2/second`` on the same route.

Fixed Window with Elastic Expiry
--------------------------------
This strategy works almost identically to the Fixed Window strategy with the exception
that each hit results in the extension of the window. This strategy works well for
creating large penalties for breaching a rate limit.

For example, if you specify a ``100/minute`` rate limit on a route and it is being
attacked at the rate of 5 hits per second for 2 minutes - the attacker will be locked
out of the resource for an extra 60 seconds after the last hit. This strategy helps
circumvent bursts.

Moving Window
-------------
.. warning:: The moving window strategy is only implemented for the ``redis`` and ``in-memory``
    storage backends. The strategy requires using a list with fast random access which
    is not very convenient to implement with a memcached storage.

This strategy is the most effective in terms of not allowing bursts to by-pass the
rate limit as the window for each limit is not fixed at the start and end of each time unit
(i.e. N/second for a moving window means N in the last 1000 milliseconds). There is
however a higher memory cost associated with this strategy as it requires ``N`` items to
be maintained in memory per resource and rate limit.

.. _keyfunc-customization:

Customization
=============


Rate limit domains
-------------------------

By default, all rate limits are applied on a per ``remote address`` basis.
However, you can easily customize your rate limits to be based on any other
characteristic of the incoming request. Both the :class:`Limiter` constructor
and the :meth:`Limiter.limit` decorator accept a keyword argument
``key_func`` that should return a string (or an object that has a string representation).

Rate limiting a route by current user (using Flask-Login)::


    @route("/test")
    @login_required
    @limiter.limit("1 per day", key_func = lambda : current_user.username)
    def test_route():
        return "42"



Rate limiting all requests by country::

    from flask import request, Flask
    import GeoIP
    gi = GeoIP.open("GeoLiteCity.dat", GeoIP.GEOIP_INDEX_CACHE | GeoIP.GEOIP_CHECK_CACHE)

    def get_request_country():
        return gi.record_by_name(request.remote_addr)['region_name']

    app = Flask(__name__)
    limiter = Limiter(app, global_limits=["10/hour"], key_func = get_request_country)



Rate limit exeeded responses
----------------------------
The default configuration results in an ``abort(409)`` being called everytime
a ratelimit is exceeded for a particular route. The exceeded limit is added to
the response and results in an response body that looks something like::

    <!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">
    <title>429 Too Many Requests</title>
    <h1>Too Many Requests</h1>
    <p>1 per 1 day</p>


If you want to configure the response you can register an error handler for the
``409`` error code in a manner similar to the following example, which returns a
json response instead::

    @app.errorhandler(429)
    def ratelimit_handler(e):
        return make_response(
                jsonify(error="ratelimit exceeded %s" % e.description)
                , 429
        )



.. _logging:

Logging
-------
Each :class:`Limiter` instance has a ``logger`` instance variable that is by
default **not** configured with a handler. You can add your own handler to obtain
log messages emitted by :mod:`flask_limiter`.

Simple stdout handler::

    limiter = Limiter(app)
    limiter.logger.addHandler(StreamHandler())

Reusing all the handlers of the ``logger`` instance of the :class:`flask.Flask` app::

    app = Flask(__name__)
    limiter = Limiter(app)
    for handler in app.logger.handlers:
        limiter.logger.addHandler(handler)

API
===

Core
----
.. autoclass:: Limiter


Exceptions
----------
.. autoexception:: ConfigurationError
.. autoexception:: RateLimitExceeded


.. include:: ../../HISTORY.rst

References
==========
* `Redis rate limiting pattern #2 <http://redis.io/commands/INCR>`_
* `DomainTools redis rate limiter <https://github.com/DomainTools/rate-limit>`_

.. include:: ../../CONTRIBUTIONS.rst
