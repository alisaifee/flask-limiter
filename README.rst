.. |travis-ci| image:: https://img.shields.io/travis/alisaifee/flask-limiter/master.svg?style=flat-square
    :target: https://travis-ci.org/#!/alisaifee/flask-limiter?branch=master
.. |coveralls| image:: https://img.shields.io/coveralls/alisaifee/flask-limiter/master.svg?style=flat-square
    :target: https://coveralls.io/r/alisaifee/flask-limiter?branch=master
.. |pypi| image:: https://img.shields.io/pypi/v/Flask-Limiter.svg?style=flat-square
    :target: https://pypi.python.org/pypi/Flask-Limiter
.. |license| image:: https://img.shields.io/pypi/l/Flask-Limiter.svg?style=flat-square
    :target: https://pypi.python.org/pypi/Flask-Limiter
.. |landscape| image:: https://landscape.io/github/alisaifee/flask-limiter/master/landscape.svg?style=flat-square
    :target: https://landscape.io/github/alisaifee/flask-limiter/master
.. |gitter| image:: https://img.shields.io/badge/gitter-join%20chat-blue.svg?style=flat-square
   :alt: Join the chat at https://gitter.im/alisaifee/flask-limiter
   :target: https://gitter.im/alisaifee/flask-limiter?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge

*************
Flask-Limiter
*************
|travis-ci| |coveralls| |landscape| |pypi| |gitter| |license| 

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
   from flask_limiter.util import get_remote_address

   app = Flask(__name__)
   limiter = Limiter(
       app,
       key_func=get_remote_address,
       default_limits=["2 per minute", "1 per second"],
   )

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
       return 'PONG'

   app.run()



Test it out. The ``fast`` endpoint respects the default rate limit while the
``slow`` endpoint uses the decorated one. ``ping`` has no rate limit associated
with it.

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
    $ curl localhost:5000/ping
    PONG
    $ curl localhost:5000/ping
    PONG
    $ curl localhost:5000/ping
    PONG
    $ curl localhost:5000/ping
    PONG




`Read the docs <http://flask-limiter.readthedocs.org>`_





