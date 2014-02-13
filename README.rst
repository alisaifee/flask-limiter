.. |travis-ci| image:: https://secure.travis-ci.org/alisaifee/flask-limiter.png?branch=master
    :target: https://travis-ci.org/#!/alisaifee/flask-limiter?branch=master
.. |coveralls| image:: https://coveralls.io/repos/alisaifee/flask-limiter/badge.png?branch=master
    :target: https://coveralls.io/r/alisaifee/flask-limiter?branch=master
.. |pypi| image:: https://pypip.in/v/flask-limiter/badge.png
    :target: https://crate.io/packages/flask-limiter/

*************
Flask-Limiter
*************
|travis-ci| |coveralls| |pypi|

Flask-Limiter provides rate limiting features to flask routes.
It has support for a configurable backend for storage
with current implementations for in-memory, redis and memcache.

Quickstart
===========

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

   app.run()


.. code-block:: bash

    $ curl localhost:5000/fast
    42
    $ curl localhost:5000/fast
    42
    $ curl localhost:5000/slow
    24
    $ curl localhost:5000/slow
    <!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">
    <title>429 Too Many Requests</title>
    <h1>Too Many Requests</h1>
    <p>1 per 1 day</p>




`Read the docs <http://flask-limiter.readthedocs.org>`_