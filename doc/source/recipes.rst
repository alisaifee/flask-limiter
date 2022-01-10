Recipes
=======

.. contents:: Some common use cases
   :backlinks: none
   :local:

.. _keyfunc-customization:

Rate Limit Key Functions
-------------------------

You can easily customize your rate limits to be based on any
characteristic of the incoming request. Both the :class:`~flask_limiter.Limiter` constructor
and the :meth:`~flask_limiter.Limiter.limit` decorator accept a keyword argument
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
    limiter = Limiter(app, default_limits=["10/hour"], key_func = get_request_country)



Custom Rate limit exceeded responses
------------------------------------
The default configuration results in an ``abort(429)`` being called every time
a rate limit is exceeded for a particular route. The exceeded limit is added to
the response and results in an response body that looks something like:

.. code:: html

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

Customizing rate limits based on response
-----------------------------------------
For scenarios where the decision to count the current request towards a rate limit
can only be made after the request has completed, a callable that accepts the current
:class:`flask.Response` object as its argument can be provided to the :meth:`~flask_limiter.Limiter.limit` or
:meth:`~flask_limiter.Limiter.shared_limit` decorators through the ``deduct_when`` keyword arugment.
A truthy response from the callable will result in a deduction from the rate limit.

As an example, to only count non `200` responses towards the rate limit


.. code-block:: python

   @app.route("..")
   @limiter.limit(
       "1/second",
       deduct_when=lambda response: response.status_code != 200
   )
   def route():
       ...


.. note:: All requests will be tested for the rate limit and rejected accordingly
 if the rate limit is already hit. The providion of the `deduct_when`
 argument only changes whether the request will count towards depleting the rate limit.


Using Flask Pluggable Views
---------------------------

If you are using a class based approach to defining view function, the regular
method of decorating a view function to apply a per route rate limit will not
work. You can add rate limits to your view classes using the following approach.


.. code-block:: python

   app = Flask(__name__)
   limiter = Limiter(app, key_func=get_remote_address)

   class MyView(flask.views.MethodView):
       decorators = [limiter.limit("10/second")]
       def get(self):
           return "get"

       def put(self):
           return "put"


.. note:: This approach is limited to either sharing the same rate limit for
 all http methods of a given :class:`flask.views.View` or applying the declared
 rate limit independently for each http method (to accomplish this, pass in ``True`` to
 the ``per_method`` keyword argument to :meth:`~flask_limiter.Limiter.limit`). Alternatively, the limit
 can be restricted to only certain http methods by passing them as a list to the `methods`
 keyword argument.


The above approach has been tested with sub-classes of  :class:`flask.views.View`,
:class:`flask.views.MethodView` and :class:`flask_restful.Resource`.

Rate limiting all routes in a :class:`flask.Blueprint`
------------------------------------------------------
:meth:`~flask_limiter.Limiter.limit`, :meth:`~flask_limiter.Limiter.shared_limit` &
:meth:`~flask_limiter.Limiter.exempt` can all be tpplied to :class:`flask.Blueprint` instances as well.
In the following example the **login** Blueprint has a special rate limit applied to all its routes, while
the **help** Blueprint is exempt from all rate limits. The **regular** Blueprint follows the default rate limits.


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


   limiter = Limiter(app, default_limits = ["1/second"], key_func=get_remote_address)
   limiter.limit("60/hour")(login)
   limiter.exempt(doc)

   app.register_blueprint(doc)
   app.register_blueprint(login)
   app.register_blueprint(regular)



.. _logging:

Logging
-------
Each :class:`~flask_limiter.Limiter` instance has a ``logger`` instance variable that is by
default **not** configured with a handler. You can add your own handler to obtain
log messages emitted by :mod:`flask_limiter`.

Simple stdout handler::

    limiter = Limiter(app, key_func=get_remote_address)
    limiter.logger.addHandler(StreamHandler())

Reusing all the handlers of the ``logger`` instance of the :class:`flask.Flask` app::

    app = Flask(__name__)
    limiter = Limiter(app, key_func=get_remote_address)
    for handler in app.logger.handlers:
        limiter.logger.addHandler(handler)




Custom error messages
---------------------
:meth:`~flask_limiter.Limiter.limit` & :meth:`~flask_limiter.Limiter.shared_limit` can be provided with an `error_message`
argument to over ride the default `n per x` error message that is returned to the calling client.
The `error_message` argument can either be a simple string or a callable that returns one.

.. code-block:: python


    app = Flask(__name__)
    limiter = Limiter(app, key_func=get_remote_address)

    def error_handler():
        return app.config.get("DEFAULT_ERROR_MESSAGE")

    @app.route("/")
    @limiter.limit("1/second", error_message='chill!')
    def index():
        ....

    @app.route("/ping")
    @limiter.limit("10/second", error_message=error_handler)
    def ping():
        ....

Custom rate limit headers
-------------------------
Though you can get pretty far with configuring the standard headers associated
with rate limiting using configuration parameters available as described under
:ref:`configuration:rate-limiting headers` - this may not be sufficient for your use case.

For such cases you can access the :attr:`~flask_limiter.Limiter.current_limit`
property from the :class:`~flask_limiter.Limiter` instance from anywhere within a :doc:`request context <flask:reqcontext>`.

As an example you could leave the built in header population disabled
and add your own with an :meth:`~flask.Flask.after_request` hook::


      app = Flask(__name__)
      limiter = Limiter(app, key_func=get_remote_address)


      @app.route("/")
      @limiter.limit("1/second")
      def index():
          ....

      @app.after_request
      def add_headers(response):
          if limiter.current_limit:
              response.headers["RemainingLimit"] = limiter.current_limit.remaining
              response.headers["ResetAt"] = limiter.current_limit.reset_at
              response.headers["MaxRequests"] = limiter.current_limit.limit.amount
              response.headers["WindowSize"] = limiter.current_limit.limit.get_expiry()
              response.headers["Breached"] = limiter.current_limit.breached
          return response

This will result in headers along the lines of::

  < RemainingLimit: 0
  < ResetAt: 1641691205
  < MaxRequests: 1
  < WindowSize: 1
  < Breached: True

.. _deploy-behind-proxy:

Deploying an application behind a proxy
---------------------------------------

If your application is behind a proxy and you are using werkzeug > 0.9+ you can use the :class:`werkzeug.middleware.proxy_fix.ProxyFix`
fixer to reliably get the remote address of the user, while protecting your application against ip spoofing via headers.


.. code-block:: python

    from flask import Flask
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    from werkzeug.middleware.proxy_fix import ProxyFix

    app = Flask(__name__)
    # for example if the request goes through one proxy
    # before hitting your application server
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)
    limiter = Limiter(app, key_func=get_remote_address)
