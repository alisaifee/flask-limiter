.. |ci| image:: https://github.com/alisaifee/flask-limiter/workflows/CI/badge.svg?branch=master
   :target: https://github.com/alisaifee/flask-limiter/actions?query=branch%3Amaster+workflow%3ACI
.. |codecov| image:: https://codecov.io/gh/alisaifee/flask-limiter/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/alisaifee/flask-limiter
.. |pypi| image:: https://img.shields.io/pypi/v/Flask-Limiter.svg?style=flat-square
   :target: https://pypi.python.org/pypi/Flask-Limiter
.. |license| image:: https://img.shields.io/pypi/l/Flask-Limiter.svg?style=flat-square
   :target: https://pypi.python.org/pypi/Flask-Limiter
.. |docs| image:: https://readthedocs.org/projects/flask-limiter/badge/?version=latest
   :target: https://flask-limiter.readthedocs.org

*************
Flask-Limiter
*************


|docs| |ci| |codecov| |pypi| |license|

Flask-Limiter provides rate limiting features to flask applications.

It allows configuring various backends to persist the rate limits, which is
provided by the `limits <https://github.com/alisaifee/limits>`_ library.

Compatibility
=============
The ``2.x`` versions of the extension only supports Pythons versions >= 3.7
and Flask >= 2.0.

If you are looking for support for older versions,
please refer to the `1.x branch <https://github.com/alisaifee/flask-limiter/tree/1.x>`_

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
