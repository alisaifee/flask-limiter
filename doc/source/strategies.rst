.. _ratelimit-strategy:

Rate limiting strategies
========================
Flask-Limiter delegates the implementation of rate limiting strategies
to the :doc:`limits:index` library.

The strategy can be selected by setting the :paramref:`flask_limiter.Limiter.strategy`
constructor argument or the :data:`RATELIMIT_STRATEGY` config.


.. note:: For more details about the implementation of each strategy
   refer to the :pypi:`limits` documentation for :doc:`limits:strategies`.


Fixed Window
------------
This strategy is the most memory‑efficient because it uses a single counter
per resource and rate limit. When the first request arrives, a window is started
for a fixed duration (e.g., for a rate limit of 10 requests per minute the window
expires in 60 seconds from the first request).
All requests in that window increment the counter and when the window expires,
the counter resets

See the :ref:`limits:strategies:fixed window` documentation in the :doc:`limits:index` library
for more details.

To select this strategy, set :paramref:`flask_limiter.Limiter.strategy` or
:data:`RATELIMIT_STRATEGY` to ``fixed-window``

Moving Window
-------------

This strategy adds each request’s timestamp to a log if the ``nth`` oldest entry (where ``n``
is the limit) is either not present or is older than the duration of the window (for example with a rate limit of
``10 requests per minute`` if there are either less than 10 entries or the 10th oldest entry is atleast
60 seconds old). Upon adding a new entry to the log "expired" entries are truncated.

See the :ref:`limits:strategies:moving window` documentation in the :doc:`limits:index` library
for more details.

To select this strategy, set :paramref:`flask_limiter.Limiter.strategy` or
:data:`RATELIMIT_STRATEGY` to ``moving-window``


Sliding Window
--------------

This strategy approximates the moving window while using less memory by maintaining
two counters:

- **Current bucket:** counts requests in the ongoing period.
- **Previous bucket:** counts requests in the immediately preceding period.

A weighted sum of these counters is computed based on the elapsed time in the current
bucket.

See the :ref:`limits:strategies:sliding window counter` documentation in the :doc:`limits:index` library
for more details.

To select this strategy, set :paramref:`flask_limiter.Limiter.strategy` or
:data:`RATELIMIT_STRATEGY` to ``sliding-window-counter``
