.. _pymemcache: https://pypi.python.org/pypi/pymemcache
.. _redis: https://pypi.python.org/pypi/redis

*************
Flask-Limiter
*************

Quickstart
==========
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


The above Flask app will have a global rate limit of 200 per day, and 50 per hour
applied to all routes. The ``slow`` route having an explicit rate limit decorator
will bypass the global rate limit and only allow 1 request per day. Every time
a request exceeds the rate limit, the view function will not get called and instead
a `429 <http://tools.ietf.org/html/rfc6585#section-4>`_ http error will be raised.

Configuration
=============
The following flask configuration values are honored by
:class:`flask_limiter.Limiter`

.. tabularcolumns:: |p{6.5cm}|p{8.5cm}|

============================== ================================================
``RATELIMIT_GLOBAL``           A comma (or some other delimiter) separated string
                               that will be used to apply a global limit on all
                               routes. If not provided, the global limits can be
                               passed to the :class:`flask_limiter.Limiter` constructor
                               as well (the values passed to the constructor take precedence
                               over those in the config). :ref:`ratelimit-string` for details.
``RATELIMIT_STORE_URL``        One of ``memory://`` or ``redis://host:port``
                               or ``memcached://host:port``. Using the redis storage
                               requires the installation of the `redis`_ package
                               while memcached relies on the `pymemcache`_ package.
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

Customization
=============

By default, all rate limits are applied on a per ``remote address`` basis.
However, you can easily customize your rate limits to be based on any other
characteristic of the incoming request. Both the :class:`flask_limiter.Limiter` constructor
and the :meth:`flask_limiter.Limiter.limit` decorator accept a keyword argument
``key_func`` that should return a string (or an object that has a string representation).


Examples
--------

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



Error Handling
==============
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
        print type(e.description)
        return make_response(
                jsonify(error="ratelimit exceeded %s" % e.description)
                , 429
        )


API
===

Core
----
.. autoclass:: flask_limiter.Limiter


Exceptions
----------
.. autoexception:: flask_limiter.ConfigurationError
.. autoexception:: flask_limiter.RateLimitExceeded

