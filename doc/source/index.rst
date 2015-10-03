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
The decorators made available as instance methods of the :class:`Limiter`
instance are

.. _ratelimit-decorator-limit:

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

.. _ratelimit-decorator-shared-limit:

:meth:`Limiter.shared_limit`
    For scenarios where a rate limit should be shared by multiple routes
    (For example when you want to protect routes using the same resource
    with an umbrella rate limit).

    Named shared limit

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


    Dynamic shared limit: when a callable is passed as scope, the return value
    of the function will be used as the scope.

      .. code-block:: python

        def host_scope():
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


    .. note:: Shared rate limits provide the same conveniences as individual rate limits

        * Can be chained with other shared limits or individual limits
        * Accept keying functions
        * Accept callables to determine the rate limit value



.. _ratelimit-decorator-exempt:

:meth:`Limiter.exempt`
  This decorator simply marks a route as being exempt from any rate limits.

.. _ratelimit-decorator-request-filter:

:meth:`Limiter.request_filter`
  This decorator simply marks a function as a filter for requests that are going
  to be tested for rate limits. If any of the request filters return ``True`` no
  rate limiting will be performed for that request. This mechanism can be used to
  create custom white lists.


        .. code-block:: python

            @limiter.request_filter
            def header_whitelist():
                return request.headers.get("X-Internal", "") == "true"

            @limiter.request_filter
            def ip_whitelist():
                return request.remote_addr == "127.0.0.1"

    In the above example, any request that contains the header ``X-Internal: true``
    or originates from localhost will not be rate limited.


.. _ratelimit-conf:

Configuration
=============
The following flask configuration values are honored by
:class:`Limiter`. If the corresponding configuration is passed in to the
:class:`Limiter` constructor, those will take precedence.

.. tabularcolumns:: |p{6.5cm}|p{8.5cm}|

============================== ================================================
``RATELIMIT_GLOBAL``           A comma (or some other delimiter) separated string
                               that will be used to apply a global limit on all
                               routes. If not provided, the global limits can be
                               passed to the :class:`Limiter` constructor
                               as well (the values passed to the constructor take precedence
                               over those in the config). :ref:`ratelimit-string` for details.
``RATELIMIT_STORAGE_URL``      One of ``memory://`` or ``redis://host:port``
                               or ``memcached://host:port``. Using the redis storage
                               requires the installation of the `redis`_ package
                               while memcached relies on the `pymemcache`_ package.
``RATELIMIT_STORAGE_OPTIONS``  A dictionary to set extra options to be passed to the
                               storage implementation upon initialization. (Useful if you're
                               subclassing :class:`limits.Storage` to create a
                               custom Storage backend.)
``RATELIMIT_STRATEGY``         The rate limiting strategy to use.  :ref:`ratelimit-strategy`
                               for details.
``RATELIMIT_HEADERS_ENABLED``  Enables returning :ref:`ratelimit-headers`. Defaults to ``False``
``RATELIMIT_ENABLED``          Overall kill switch for rate limits. Defaults to ``True``
``RATELIMIT_HEADER_LIMIT``     Header for the current rate limit. Defaults to ``X-RateLimit-Limit``
``RATELIMIT_HEADER_RESET``     Header for the reset time of the current rate limit. Defaults to ``X-RateLimit-Reset``
``RATELIMIT_HEADER_REMAINING`` Header for the number of requests remaining in the current rate limit. Defaults to ``X-RateLimit-Remaining``
``RATELIMIT_SWALLOW_ERRORS``   Whether to allow failures while attempting to perform a rate limit
                               such as errors with downstream storage. Setting this value to ``True``
                               will effectively disable rate limiting for requests where an error has
                               occurred.
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
   global rate limit strings will however raise an exception as they are evaluated
   early enough to not cause disruption to a running application.


.. _ratelimit-strategy:

Rate limiting strategies
========================
Flask-Limiter comes with three different rate limiting strategies built-in. Pick
the one that works for your use-case by specifying it in your flask config as
``RATELIMIT_STRATEGY`` (one of ``fixed-window``, ``fixed-window-elastic-expiry``,
or ``moving-window``), or as a constructor keyword argument. The default
configuration is ``fixed-window``.


Fixed Window
------------
This is the most memory efficient strategy to use as it maintains one counter
per resource and rate limit. It does however have its drawbacks as it allows
bursts within each window - thus allowing an 'attacker' to by-pass the limits.
The effects of these bursts can be partially circumvented by enforcing multiple
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

This strategy is the most effective for preventing bursts from by-passing the
rate limit as the window for each limit is not fixed at the start and end of each time unit
(i.e. N/second for a moving window means N in the last 1000 milliseconds). There is
however a higher memory cost associated with this strategy as it requires ``N`` items to
be maintained in memory per resource and rate limit.

.. _ratelimit-headers:

Rate-limiting Headers
=====================

If the configuration is enabled, information about the rate limit with respect to the
route being requested will be added to the response headers. Since multiple rate limits
can be active for a given route - the rate limit with the lowest time granularity will be
used in the scenario when the request does not breach any rate limits.

.. tabularcolumns:: |p{6.5cm}|p{8.5cm}|

============================== ================================================
``X-RateLimit-Limit``          The total number of requests allowed for the
                               active window
``X-RateLimit-Remaining``      The number of requests remaining in the active
                               window.
``X-RateLimit-Reset``          UTC seconds since epoch when the window will be
                               reset.
============================== ================================================

.. warning:: Enabling the headers has an additional cost with certain storage / strategy combinations.

    * Memcached + Fixed Window: an extra key per rate limit is stored to calculate
      ``X-RateLimit-Reset``
    * Redis + Moving Window: an extra call to redis is involved during every request
      to calculate ``X-RateLimit-Remaining`` and ``X-RateLimit-Reset``

The header names can be customised if required by either using the flask configuration (:ref:`ratelimit-conf`)
values or by setting the ``header_mapping`` property of the :class:`Limiter` as follows::

    from flask.ext.limiter import Limiter, HEADERS
    limiter = Limiter()
    limiter.header_mapping = {
        HEADERS.LIMIT : "X-My-Limit",
        HEADERS.RESET : "X-My-Reset",
        HEADERS.REMAINING: "X-My-Remaining"
    }
    # or by only partially specifying the overrides
    limiter.header_mapping[HEADERS.LIMIT] = 'X-My-Limit'




.. _keyfunc-customization:

Recipes
=======


Custom Rate limit domains
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



Custom Rate limit exceeded responses
------------------------------------
The default configuration results in an ``abort(429)`` being called every time
a rate limit is exceeded for a particular route. The exceeded limit is added to
the response and results in an response body that looks something like::

    <!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">
    <title>429 Too Many Requests</title>
    <h1>Too Many Requests</h1>
    <p>1 per 1 day</p>


If you want to configure the response you can register an error handler for the
``429`` error code in a manner similar to the following example, which returns a
json response instead::

    @app.errorhandler(429)
    def ratelimit_handler(e):
        return make_response(
                jsonify(error="ratelimit exceeded %s" % e.description)
                , 429
        )



Using Flask Pluggable Views
---------------------------

If you are using a class based approach to defining view function, the regular
method of decorating a view function to apply a per route rate limit will not
work. You can add rate limits to your view classes using the following approach.


.. code-block:: python

    app = Flask(__name__)
    limiter = Limiter(app)

    class MyView(flask.views.MethodView):
        decorators = [limiter.limit("10/second")]
        def get(self):
            return "get"

        def put(self):
            return "put"


.. note:: This approach is limited to either sharing the same rate limit for
 all http methods of a given :class:`flask.views.View` or applying the declared
 rate limit independently for each http method (to accomplish this, pass in ``True`` to
 the ``per_method`` keyword argument to :meth:`Limiter.limit`). Alternatively, the limit
 can be restricted to only certain http methods by passing them as a list to the `methods`
 keyword argument.


The above approach has been tested with sub-classes of  :class:`flask.views.View`,
:class:`flask.views.MethodView` and :class:`flask.ext.restful.Resource`.

Rate limiting all routes in a :class:`flask.Blueprint`
------------------------------------------------------
:meth:`Limiter.limit`, :meth:`Limiter.shared_limit` & :meth:`Limiter.exempt` can
all be applied to :class:`flask.Blueprint` instances as well. In the following example
the **login** Blueprint has a special rate limit applied to all its routes, while the **help**
Blueprint is exempt from all rate limits. The **regular** Blueprint follows the global rate limits.


    .. code-block:: python


        app = Flask(__name__)
        login = Blueprint("login", __name__, url_prefix = "/login")
        regular = Blueprint("regular", __name__, url_prefix = "/regular")
        doc = Blueprint("doc", __name__, url_prefix = "/doc")

        @doc.route("/")
        def doc_index():
            return "doc"

        @regular.route("/")
        def regular_index():
            return "regular"

        @login.route("/")
        def login_index():
            return "login"


        limiter = Limiter(app, global_limits = ["1/second"])
        limiter.limit("60/hour")(login)
        limiter.exempt(doc)

        app.register_blueprint(doc)
        app.register_blueprint(login)
        app.register_blueprint(regular)



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




Custom error messages
---------------------
:meth:`Limiter.limit` & :meth:`Limiter.shared_limit` can be provided with an `error_message`
argument to over ride the default `n per x` error message that is returned to the calling client.
The `error_message` argument can either be a simple string or a callable that returns one.

    .. code-block:: python


        app = Flask(__name__)
        limiter = Limiter(app)

        def error_handler():
            return app.config.get("DEFAULT_ERROR_MESSAGE")

        @limiter.limit("1/second", error_message='chill!')
        @app.route("/")
        def index():
            ....

        @limiter.limit("10/second", error_message=error_handler)
        @app.route("/ping")
        def ping():
            ....



API
===

Core
----
.. autoclass:: Limiter


Exceptions
----------
.. autoexception:: RateLimitExceeded


.. include:: ../../HISTORY.rst

References
==========
* `Redis rate limiting pattern #2 <http://redis.io/commands/INCR>`_
* `DomainTools redis rate limiter <https://github.com/DomainTools/rate-limit>`_
* `limits: python rate limiting utilities <https://limits.readthedocs.org>`_

.. include:: ../../CONTRIBUTIONS.rst
