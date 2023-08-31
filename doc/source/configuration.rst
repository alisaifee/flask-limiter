.. _RFC2616: https://tools.ietf.org/html/rfc2616#section-14.37
.. _ratelimit-conf:

Configuration
=============

Using Flask Config
------------------
The following :doc:`Flask Configuration <flask:config>` values are honored by
:class:`~flask_limiter.Limiter`. If the corresponding configuration value is also present
as an argument to the :class:`~flask_limiter.Limiter` constructor, the constructor argument will
take priority.

.. list-table::

   * - .. data:: RATELIMIT_ENABLED

       Constructor argument: :paramref:`~flask_limiter.Limiter.enabled`

     - Overall kill switch for rate limits. Defaults to ``True``
   * - .. data:: RATELIMIT_KEY_FUNC

       Constructor argument: :paramref:`~flask_limiter.Limiter.key_func`

     - A callable that returns the domain to rate limit (e.g. username, ip address etc)
   * - .. data:: RATELIMIT_KEY_PREFIX

       Constructor argument: :paramref:`~flask_limiter.Limiter.key_prefix`

     - Prefix that is prepended to each stored rate limit key and app context
       global name. This can be useful when using a shared storage for multiple
       applications or rate limit domains. For multi-instance use cases, explicitly
       pass ``key_prefix`` keyword argument to :class:`~flask_limiter.Limiter` constructor instead.
   * - .. data:: RATELIMIT_APPLICATION

       Constructor argument: :paramref:`~flask_limiter.Limiter.application_limits`

     - A comma (or some other delimiter) separated string that will be used to
       apply limits to the application as a whole (i.e. shared by all routes).
   * - .. data:: RATELIMIT_APPLICATION_PER_METHOD

       Constructor argument: :paramref:`~flask_limiter.Limiter.application_limits_per_method`

     - Whether application limits are applied per method, per route or as a combination
       of all method per route.
   * - .. data:: RATELIMIT_APPLICATION_EXEMPT_WHEN

       Constructor argument: :paramref:`~flask_limiter.Limiter.application_limits_exempt_when`

     - A function that should return a truthy value if the application rate limit(s)
       should be skipped for the current request. This callback is called from the
       :doc:`flask request context <flask:reqcontext>` :meth:`~flask.Flask.before_request` hook.
   * - .. data:: RATELIMIT_APPLICATION_DEDUCT_WHEN

       Constructor argument: :paramref:`~flask_limiter.Limiter.application_limits_deduct_when`

     - A function that should return a truthy value if a deduction should be made
       from the application rate limit(s) for the current request. This callback is called
       from the :doc:`flask request context <flask:reqcontext>` :meth:`~flask.Flask.after_request` hook.
   * - .. data:: RATELIMIT_APPLICATION_COST

       Constructor argument: :paramref:`~flask_limiter.Limiter.application_limits_cost`

     - The cost of a hit to the application wide shared limit as an integer or a function
       that takes no parameters and returns the cost as an integer (Default: 1)
   * - .. data:: RATELIMIT_DEFAULT

       Constructor argument: :paramref:`~flask_limiter.Limiter.default_limits`

     - A comma (or some other delimiter) separated string that will be used to
       apply a default limit on all routes that are otherwise not decorated with
       an explicit rate limit. If not provided, the default limits can be
       passed to the :class:`~flask_limiter.Limiter` constructor as well (the values passed to the
       constructor take precedence over those in the config).
       :ref:`ratelimit-string` for details.
   * - .. data:: RATELIMIT_DEFAULTS_PER_METHOD

       Constructor argument: :paramref:`~flask_limiter.Limiter.default_limits_per_method`

     - Whether default limits are applied per method, per route or as a combination
       of all method per route.
   * - .. data:: RATELIMIT_DEFAULTS_COST

       Constructor argument: :paramref:`~flask_limiter.Limiter.default_limits_cost`

     - The cost of a hit to the default limits as an integer or a function
       that takes no parameters and returns the cost as an integer (Default: 1)
   * - .. data:: RATELIMIT_DEFAULTS_EXEMPT_WHEN

       Constructor argument: :paramref:`~flask_limiter.Limiter.default_limits_exempt_when`

     - A function that should return a truthy value if the default rate limit(s)
       should be skipped for the current request. This callback is called from the
       :doc:`flask request context <flask:reqcontext>` :meth:`~flask.Flask.before_request` hook.
   * - .. data:: RATELIMIT_DEFAULTS_DEDUCT_WHEN

       Constructor argument: :paramref:`~flask_limiter.Limiter.default_limits_deduct_when`

     - A function that should return a truthy value if a deduction should be made
       from the default rate limit(s) for the current request. This callback is called
       from the :doc:`flask request context <flask:reqcontext>` :meth:`~flask.Flask.after_request` hook.
   * - .. data:: RATELIMIT_STORAGE_URI

       Constructor argument: :paramref:`~flask_limiter.Limiter.storage_uri`

     - A storage location conforming to the scheme in :ref:`limits:storage:storage scheme`.
       A basic in-memory storage can be used by specifying ``memory://`` but it
       should be used with caution in any production setup since:

       #. Each application process will have it's own storage
       #. The state of the rate limits will not persist beyond the process' life-time.

       Other supported backends include:

       - Memcached: ``memcached://host:port``
       - MongoDB: ``mongodb://host:port``
       - Redis: ``redis://host:port``

       For specific examples and requirements of supported backends please
       refer to :ref:`limits:storage:storage scheme` and the :doc:`limits <limits:storage>` library.
   * - .. data:: RATELIMIT_STORAGE_OPTIONS

       Constructor argument: :paramref:`~flask_limiter.Limiter.storage_options`

     - A dictionary to set extra options to be passed to the  storage implementation
       upon initialization.
   * - .. data:: RATELIMIT_REQUEST_IDENTIFIER

       Constructor argument: :paramref:`~flask_limiter.Limiter.request_identifier`

     - A callable that returns the unique identity of the current request. Defaults to :attr:`flask.Request.endpoint`
   * - .. data:: RATELIMIT_STRATEGY

       Constructor argument: :paramref:`~flask_limiter.Limiter.strategy`

     - The rate limiting strategy to use.  :ref:`ratelimit-strategy`
       for details.
   * - .. data:: RATELIMIT_HEADERS_ENABLED

       Constructor argument: :paramref:`~flask_limiter.Limiter.headers_enabled`

     - Enables returning :ref:`ratelimit-headers`. Defaults to ``False``
   * - .. data:: RATELIMIT_HEADER_LIMIT

       Constructor argument: :paramref:`~flask_limiter.Limiter.header_name_mapping`

     - Header for the current rate limit. Defaults to ``X-RateLimit-Limit``
   * - .. data:: RATELIMIT_HEADER_RESET

       Constructor argument: :paramref:`~flask_limiter.Limiter.header_name_mapping`

     - Header for the reset time of the current rate limit. Defaults to ``X-RateLimit-Reset``
   * - .. data:: RATELIMIT_HEADER_REMAINING

       Constructor argument: :paramref:`~flask_limiter.Limiter.header_name_mapping`

     - Header for the number of requests remaining in the current rate limit. Defaults to ``X-RateLimit-Remaining``
   * - .. data:: RATELIMIT_HEADER_RETRY_AFTER

       Constructor argument: :paramref:`~flask_limiter.Limiter.header_name_mapping`

     - Header for when the client should retry the request. Defaults to ``Retry-After``
   * - .. data:: RATELIMIT_HEADER_RETRY_AFTER_VALUE

       Constructor argument: :paramref:`~flask_limiter.Limiter.retry_after`

     - Allows configuration of how the value of the ``Retry-After`` header is rendered.
       One of ``http-date`` or ``delta-seconds``. (`RFC2616`_).
   * - .. data:: RATELIMIT_SWALLOW_ERRORS

       Constructor argument: :paramref:`~flask_limiter.Limiter.swallow_errors`

     - Whether to allow failures while attempting to perform a rate limit
       such as errors with downstream storage. Setting this value to ``True``
       will effectively disable rate limiting for requests where an error has
       occurred.
   * - .. data:: RATELIMIT_IN_MEMORY_FALLBACK_ENABLED

       Constructor argument: :paramref:`~flask_limiter.Limiter.in_memory_fallback_enabled`

     - ``True``/``False``. If enabled an in memory rate limiter will be used
       as a fallback when the configured storage is down. Note that, when used in
       combination with ``RATELIMIT_IN_MEMORY_FALLBACK`` the original rate limits
       will not be inherited and the values provided in
   * - .. data:: RATELIMIT_IN_MEMORY_FALLBACK

       Constructor argument: :paramref:`~flask_limiter.Limiter.in_memory_fallback`

     - A comma (or some other delimiter) separated string
       that will be used when the configured storage is down.
   * - .. data:: RATELIMIT_FAIL_ON_FIRST_BREACH

       Constructor argument: :paramref:`~flask_limiter.Limiter.fail_on_first_breach`

     - Whether to stop processing remaining limits after the first breach.
       Default to ``True``
   * - .. data:: RATELIMIT_ON_BREACH_CALLBACK

       Constructor argument: :paramref:`~flask_limiter.Limiter.on_breach_callback`

     - A function that will be called when any limit in this
       extension is breached.
   * - .. data:: RATELIMIT_META

       Constructor argument: :paramref:`~flask_limiter.Limiter.meta_limits`

     - A comma (or some other delimiter) separated string that will be used to
       control the upper limit of a requesting client hitting any configured rate limit.
       Once a meta limit is exceeded all subsequent requests will raise a
       :class:`~flask_limiter.RateLimitExceeded` for the duration of the meta limit window.
   * - .. data:: RATELIMIT_ON_META_BREACH_CALLBACK

       Constructor argument: :paramref:`~flask_limiter.Limiter.on_meta_breach_callback`

     - A function that will be called when a meta limit in this
       extension is breached.

.. _ratelimit-string:

Rate limit string notation
--------------------------

Rate limits are specified as strings following the format::

    [count] [per|/] [n (optional)] [second|minute|hour|day|month|year][s]

You can combine multiple rate limits by separating them with a delimiter of your
choice.

Examples
^^^^^^^^

* ``10 per hour``
* ``10 per 2 hours``
* ``10/hour``
* ``5/2 seconds;10/hour;100/day;2000 per year``
* ``100/day, 500/7 days``

.. warning:: If rate limit strings that are provided to the :meth:`~flask_limiter.Limiter.limit`
   decorator are malformed and can't be parsed the decorated route will fall back
   to the default rate limit(s) and an ``ERROR`` log message will be emitted. Refer
   to :ref:`logging` for more details on capturing this information. Malformed
   default rate limit strings will however raise an exception as they are evaluated
   early enough to not cause disruption to a running application.


.. _ratelimit-headers:

Rate-limiting Headers
---------------------

If the configuration is enabled, information about the rate limit with respect to the
route being requested will be added to the response headers. Since multiple rate limits
can be active for a given route - the rate limit with the lowest time granularity will be
used in the scenario when the request does not breach any rate limits.

.. tabularcolumns:: |p{8cm}|p{8.5cm}|

============================== ================================================
``X-RateLimit-Limit``          The total number of requests allowed for the
                               active window
``X-RateLimit-Remaining``      The number of requests remaining in the active
                               window.
``X-RateLimit-Reset``          UTC seconds since epoch when the window will be
                               reset.
``Retry-After``                Seconds to retry after or the http date when the
                               Rate Limit will be reset. The way the value is presented
                               depends on the configuration value set in :data:`RATELIMIT_HEADER_RETRY_AFTER_VALUE`
                               and defaults to `delta-seconds`.
============================== ================================================


The header names can be customised if required by either using the flask configuration (
:attr:`RATELIMIT_HEADER_LIMIT`,
:attr:`RATELIMIT_HEADER_RESET`,
:attr:`RATELIMIT_HEADER_RETRY_AFTER`,
:attr:`RATELIMIT_HEADER_REMAINING`
)
values or by providing the :paramref:`~flask_limiter.Limiter.header_name_mapping` argument
to the extension constructor as follows::

    from flask_limiter import Limiter, HEADERS
    limiter = Limiter(header_name_mapping={
         HEADERS.LIMIT : "X-My-Limit",
         HEADERS.RESET : "X-My-Reset",
         HEADERS.REMAINING: "X-My-Remaining"
      }
    )






