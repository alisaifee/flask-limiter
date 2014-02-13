.. |travis-ci| image:: https://secure.travis-ci.org/alisaifee/flask-limiter.png?branch=master
    :target: https://travis-ci.org/#!/alisaifee/flask-limiter?branch=master
.. |coveralls| image:: https://coveralls.io/repos/alisaifee/flask-limiter/badge.png?branch=master
    :target: https://coveralls.io/r/alisaifee/flask-limiter?branch=master
.. |pypi| image:: https://pypip.in/v/Flask-Limiter/badge.png
    :target: https://crate.io/packages/Flask-Limiter/

*************
Flask-Limiter
*************
|travis-ci| |coveralls| |pypi|

Flask-Limiter provides rate limiting features to flask routes.
It has support for a configurable backend for storage
with current implementations for in-memory, redis and memcache.

Quickstart
===========

Add the rate limiter to your flask app. The following example uses the default
in memory implementation for storage.

.. code-block:: python

   from flask import Flask
   from flask_limiter import Limiter

   app = Flask(__name__)
   limiter = Limiter(app, global_limits=["2 per minute", "1 per second"])

   @app.route("/slow")
   @limiter.limit("1 per day")
   def slow():
       return "24"

   @app.route("/fast")
   def fast():
       return "42"

   app.run()



Test it out. The ``fast`` endpoint respects the global rate limit while the
``slow`` endpoint uses the decorated one.

.. code-block:: bash

    $ curl localhost:5000/fast
    42
    $ curl localhost:5000/fast
    42
    $ curl localhost:5000/fast
    <!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">
    <title>429 Too Many Requests</title>
    <h1>Too Many Requests</h1>
    <p>2 per 1 minute</p>
    $ curl localhost:5000/slow
    24
    $ curl localhost:5000/slow
    <!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">
    <title>429 Too Many Requests</title>
    <h1>Too Many Requests</h1>
    <p>1 per 1 day</p>




`Read the docs <http://flask-limiter.readthedocs.org>`_


