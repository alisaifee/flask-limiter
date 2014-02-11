Welcome to Flask-Limiter's documentation!
=========================================

Example use
-----------
.. code-block:: python

   from flask import Flask
   from flask_limiter import Limiter

   app = Flask(__name__)
   limiter = Limiter(Flask)
   limiter.global_limits += "100 per day"

   @app.route("/slow")
   @limiter.limit("1 per day")
   def slow():
       return 24

   @app.route("/fast")
   def fast():
       return 42


Configuration
-------------
The following flask configuration values are honored by
:class:`~flask_limiter.Limiter`

.. tabularcolumns:: |p{6.5cm}|p{8.5cm}|

============================== ================================================
``RATELIMIT_GLOBAL``           The size of the random integer to be used when
                               generating random session ids through
                               :func:`~flaskext.kvsession.generate_session_key`
                               . Defaults to 64.
``RATELIMIT_STORE_URL``        An object supporting
                               :func:`random.getrandbits`, used as a random
                               source by the module. Defaults to an instance of
                               :class:`random.SystemRandom`.
============================== ================================================

API reference
-------------
.. automodule:: flask_ratelimits
    :members:


