*****************************************
Welcome to Flask-Limiter's documentation!
*****************************************

Quickstart
==========
.. code-block:: python

   from flask import Flask
   from flask_limiter import Limiter

   app = Flask(__name__)
   limiter = Limiter(Flask, "200 per day", "50 per hour")

   @app.route("/slow")
   @limiter.limit("1 per day")
   def slow():
       return 24

   @app.route("/fast")
   def fast():
       return 42


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
                               as well.
``RATELIMIT_STORE_URL``        One of ``memory://`` or ``redis://host:port``
                               or ``memcache://host:port``
============================== ================================================







API
===

Core
----
.. autoclass:: flask_limiter.Limiter


Exceptions
----------
.. autoexception:: flask_limiter.ConfigurationError
.. autoexception:: flask_limiter.RateLimitExceeded

