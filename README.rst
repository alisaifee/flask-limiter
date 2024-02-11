.. |ci| image:: https://github.com/alisaifee/flask-limiter/workflows/CI/badge.svg?branch=master
   :target: https://github.com/alisaifee/flask-limiter/actions?query=branch%3Amaster+workflow%3ACI
.. |codecov| image:: https://codecov.io/gh/alisaifee/flask-limiter/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/alisaifee/flask-limiter
.. |pypi| image:: https://img.shields.io/pypi/v/Flask-Limiter.svg?style=flat-square
   :target: https://pypi.python.org/pypi/Flask-Limiter
.. |license| image:: https://img.shields.io/pypi/l/Flask-Limiter.svg?style=flat-square
   :target: https://pypi.python.org/pypi/Flask-Limiter
.. |docs| image:: https://readthedocs.org/projects/flask-limiter/badge/?version=latest
   :target: https://flask-limiter.readthedocs.org/en/latest

*************
Flask-Limiter
*************


|docs| |ci| |codecov| |pypi| |license|

**Flask-Limiter** adds rate limiting to `Flask <https://flask.palletsprojects.com>`_ applications.

You can configure rate limits at different levels such as:

- Application wide global limits per user
- Default limits per route
- By `Blueprints <https://flask-limiter.readthedocs.io/en/latest/recipes.html#rate-limiting-all-routes-in-a-blueprint>`_
- By `Class-based views <https://flask-limiter.readthedocs.io/en/latest/recipes.html#using-flask-pluggable-views>`_
- By `individual routes <https://flask-limiter.readthedocs.io/en/latest/index.html#decorators-to-declare-rate-limits>`_

**Flask-Limiter** can be `configured <https://flask-limiter.readthedocs.io/en/latest/configuration.html>`_ to fit your application in many ways, including:

- Persistance to various commonly used `storage backends <https://flask-limiter.readthedocs.io/en/latest/#configuring-a-storage-backend>`_
  (such as Redis, Memcached, MongoDB & Etcd)
  via `limits <https://limits.readthedocs.io/en/stable/storage.html>`__
- Any rate limiting strategy supported by `limits <https://limits.readthedocs.io/en/stable/strategies.html>`__

Follow the quickstart below to get started or `read the documentation <http://flask-limiter.readthedocs.org/en/latest>`_ for more details.


Quickstart
===========

Install
-------
.. code-block:: bash

    pip install Flask-Limiter

Add the rate limiter to your flask app
---------------------------------------
.. code-block:: python

   # app.py

   from flask import Flask
   from flask_limiter import Limiter
   from flask_limiter.util import get_remote_address

   app = Flask(__name__)
   limiter = Limiter(
       get_remote_address,
       app=app,
       default_limits=["2 per minute", "1 per second"],
       storage_uri="memory://",
       # Redis
       # storage_uri="redis://localhost:6379",
       # Redis cluster
       # storage_uri="redis+cluster://localhost:7000,localhost:7001,localhost:70002",
       # Memcached
       # storage_uri="memcached://localhost:11211",
       # Memcached Cluster
       # storage_uri="memcached://localhost:11211,localhost:11212,localhost:11213",
       # MongoDB
       # storage_uri="mongodb://localhost:27017",
       # Etcd
       # storage_uri="etcd://localhost:2379",
       strategy="fixed-window", # or "moving-window"
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

Inspect the limits using the command line interface
---------------------------------------------------
.. code-block:: bash

   $ FLASK_APP=app:app flask limiter limits

   app
   ├── fast: /fast
   │   ├── 2 per 1 minute
   │   └── 1 per 1 second
   ├── ping: /ping
   │   └── Exempt
   └── slow: /slow
       └── 1 per 1 day

Run the app
-----------
.. code-block:: bash

   $ FLASK_APP=app:app flask run


Test it out
-----------
The ``fast`` endpoint respects the default rate limit while the
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




