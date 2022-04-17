Recipes
=======
.. currentmodule:: flask_limiter

.. _keyfunc-customization:

Rate Limit Key Functions
-------------------------

You can easily customize your rate limits to be based on any
characteristic of the incoming request. Both the :class:`~Limiter` constructor
and the :meth:`~Limiter.limit` decorator accept a keyword argument
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
The default configuration results in a :exc:`RateLimitExceeded` exception being
thrown (**which effectively halts any further processing and a response with status `429`**).

The exceeded limit is added to the response and results in an response body that looks something like:

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

Customizing the cost of a request
---------------------------------
By default whenever a request is served a **cost** of ``1`` is charged for
each rate limit that applies within the context of that request.

There may be situations where a different value should be used.

The :meth:`~flask_limiter.Limiter.limit` and :meth:`~flask_limiter.Limiter.shared_limit`
decorators both accept a ``cost`` parameter which accepts either a static :class:`int` or
a callable that returns an :class:`int`.

As an example, the following configuration will result in a double penalty whenever
``Some reason`` is true ::

    from flask import request, current_app

    def my_cost_function() -> int:
        if .....: # Some reason
            return  2
        return 1

    @app.route("/")
    @limiter.limit("100/second", cost=my_cost_function)
    def root():
        ...

A similar approach can be used for both default and application level limits by
providing either a cost function to the :class:`~flask_limiter.Limiter` constructor
via the :paramref:`~flask_limiter.Limiter.default_limits_cost` or
:paramref:`~flask_limiter.Limiter.application_limits_cost` parameters.

Customizing rate limits based on response
-----------------------------------------
For scenarios where the decision to count the current request towards a rate limit
can only be made after the request has completed, a callable that accepts the current
:class:`flask.Response` object as its argument can be provided to the :meth:`~Limiter.limit` or
:meth:`~Limiter.shared_limit` decorators through the ``deduct_when`` keyword arugment.
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


`deduct_when` can also be provided for default limits by providing the
:paramref:`~flask_limiter.Limiter.default_limits_deduct_when` paramter
to the :class:`~flask_limiter.Limiter` constructor.


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
 the ``per_method`` keyword argument to :meth:`~Limiter.limit`). Alternatively, the limit
 can be restricted to only certain http methods by passing them as a list to the `methods`
 keyword argument.


The above approach has been tested with sub-classes of  :class:`flask.views.View`,
:class:`flask.views.MethodView` and :class:`flask_restful.Resource`.

Rate limiting all routes in a :class:`~flask.Blueprint`
-------------------------------------------------------

.. warning:: :class:`~flask.Blueprint` instances that are registered on another blueprint
   instead of on the main :class:`~flask.Flask` instance had not been considered
   upto :ref:`changelog:v2.3.0`. Effectively **they neither inherited** the rate limits
   explicitely registered on the parent :class:`~flask.Blueprint` **nor were they
   exempt** from rate limits if the parent had been marked exempt.
   (See :issue:`326`, and the :ref:`recipes:nested blueprints` section below).

:meth:`~Limiter.limit`, :meth:`~Limiter.shared_limit` &
:meth:`~Limiter.exempt` can all be tpplied to :class:`flask.Blueprint` instances as well.
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


Nested Blueprints
^^^^^^^^^^^^^^^^^
.. versionadded:: 2.3.0

`Nested Blueprints <https://flask.palletsprojects.com/en/latest/blueprints/#nesting-blueprints>`__
require some special considerations.

=====================================
Exempting routes in nested Blueprints
=====================================

Expanding the example from the Flask documentation::

    parent = Blueprint('parent', __name__, url_prefix='/parent')
    child = Blueprint('child', __name__, url_prefix='/child')
    parent.register_blueprint(child)

    limiter.exempt(parent)

    app.register_blueprint(parent)

Routes under the ``child`` blueprint **do not** automatically get exempted by default
and have to be marked exempt explicitly. This behavior is to maintain backward compatibility
and can be opted out of by adding :attr:`~flask_limiter.ExemptionScope.DESCENDENTS`
to :paramref:`~Limiter.exempt.flags` when calling :meth:`Limiter.exempt`::

    limiter.exempt(
        parent,
        flags=ExemptionScope.DEFAULT | ExemptionScope.APPLICATION | ExemptionScope.DESCENDENTS
    )

===========================================================
Explicitly setting limits / exemptions on nested Blueprints
===========================================================

Using combinations of :paramref:`~Limiter.limit.override_defaults` parameter
when explicitely declaring limits on Blueprints and the :paramref:`~Limiter.exempt.flags`
parameter when exempting Blueprints with :meth:`~Limiter.exempt`
the resolution of inherited and descendent limits within the scope of a Blueprint
can be controlled.

Here's a slightly involved example::

    limiter = Limiter(
        ...,
        default_limits = ["100/hour"],
        application_limits = ["100/minute"]
    )

    parent = Blueprint('parent', __name__, url_prefix='/parent')
    child = Blueprint('child', __name__, url_prefix='/child')
    grandchild = Blueprint('grandchild', __name__, url_prefix='/grandchild')

    health = Blueprint('health', __name__, url_prefix='/health')

    parent.register_blueprint(child)
    parent.register_blueprint(health)
    child.register_blueprint(grandchild)
    child.register_blueprint(health)
    grandchild.register_blueprint(health)

    app.register_blueprint(parent)

    limiter.limit("2/minute")(parent)
    limiter.limit("1/second", override_defaults=False)(child)
    limiter.limit("10/minute")(grandchild)

    limiter.exempt(
        health,
        flags=ExemptionScope.DEFAULT|ExemptionScope.APPLICATION|ExemptionScope.ANCESTORS
    )

Effectively this means:

#. Routes under ``parent`` will override the application defaults and will be
   limited to ``2 per minute``

#. Routes under ``child`` will respect both the parent and the application defaults
   and effectively be limited to ``At most 1 per second, 2 per minute and 100 per hour``

#. Routes under ``grandchild`` will not inherit either the limits from `child` or `parent`
   or the application defaults and allow ``10 per minute``

#. All calls to ``/health/`` will be exempt from all limits (including any limits that would
   otherwise be inherited from the Blueprints it is nested under due to the addition of the
   :class:`~ExemptionScope.ANCESTORS` flag).

.. note:: Only calls to `/health` will be exempt from the application wide global
   limit of `100/minute`.

.. _logging:

Logging
-------
Each :class:`~Limiter` instance has a ``logger`` instance variable that is by
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
:meth:`~Limiter.limit` & :meth:`~Limiter.shared_limit` can be provided with an `error_message`
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

For such cases you can access the :attr:`~Limiter.current_limit`
property from the :class:`~Limiter` instance from anywhere within a :doc:`request context <flask:reqcontext>`.

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
