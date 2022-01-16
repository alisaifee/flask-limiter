"""
the flask extension
"""
import datetime
import enum
import itertools
import logging
import time
from functools import wraps
from typing import Callable, Dict, List, Optional, Set, Tuple, Union, cast
from weakref import ref

from flask import Blueprint, Flask, Response, current_app, g, request
from limits import RateLimitItem
from limits.errors import ConfigurationError
from limits.storage import MemoryStorage, Storage, storage_from_string
from limits.strategies import STRATEGIES, RateLimiter
from werkzeug.http import http_date, parse_date

from flask_limiter.wrappers import Limit, LimitGroup

from .errors import RateLimitExceeded


class C:
    ENABLED = "RATELIMIT_ENABLED"
    HEADERS_ENABLED = "RATELIMIT_HEADERS_ENABLED"
    STORAGE_URI = "RATELIMIT_STORAGE_URI"
    STORAGE_URL = "RATELIMIT_STORAGE_URL"  # Deprecated due to inconsistency.
    STORAGE_OPTIONS = "RATELIMIT_STORAGE_OPTIONS"
    STRATEGY = "RATELIMIT_STRATEGY"
    DEFAULT_LIMITS = "RATELIMIT_DEFAULT"
    DEFAULT_LIMITS_PER_METHOD = "RATELIMIT_DEFAULTS_PER_METHOD"
    DEFAULT_LIMITS_EXEMPT_WHEN = "RATELIMIT_DEFAULTS_EXEMPT_WHEN"
    DEFAULT_LIMITS_DEDUCT_WHEN = "RATELIMIT_DEFAULTS_DEDUCT_WHEN"
    APPLICATION_LIMITS = "RATELIMIT_APPLICATION"
    HEADER_LIMIT = "RATELIMIT_HEADER_LIMIT"
    HEADER_REMAINING = "RATELIMIT_HEADER_REMAINING"
    HEADER_RESET = "RATELIMIT_HEADER_RESET"
    SWALLOW_ERRORS = "RATELIMIT_SWALLOW_ERRORS"
    IN_MEMORY_FALLBACK = "RATELIMIT_IN_MEMORY_FALLBACK"
    IN_MEMORY_FALLBACK_ENABLED = "RATELIMIT_IN_MEMORY_FALLBACK_ENABLED"
    HEADER_RETRY_AFTER = "RATELIMIT_HEADER_RETRY_AFTER"
    HEADER_RETRY_AFTER_VALUE = "RATELIMIT_HEADER_RETRY_AFTER_VALUE"
    KEY_PREFIX = "RATELIMIT_KEY_PREFIX"
    FAIL_ON_FIRST_BREACH = "RATELIMIT_FAIL_ON_FIRST_BREACH"


class HEADERS(enum.Enum):
    """
    Enumeration of supported rate limit related headers to
    be used when configuring via :paramref:`~flask_limiter.Limiter.header_name_mapping`
    """

    #: Timestamp at which this rate limit will be reset
    RESET = "X-RateLimit-Reset"
    #: Remaining number of requests within the current window
    REMAINING = "X-RateLimit-Remaining"
    #: Total number of allowed requests within a window
    LIMIT = "X-RateLimit-Limit"
    #: Number of seconds to retry after at
    RETRY_AFTER = "Retry-After"


class RequestLimit:
    """
    Provides details of a rate limit within the context of a request
    """

    #: The instance of the rate limit
    limit: RateLimitItem

    #: The full key for the request against which the rate limit is tested
    key: str

    #: Whether the limit was breached within the context of this request
    breached: bool

    def __init__(
        self,
        limiter: RateLimiter,
        limit: RateLimitItem,
        request_args: List[str],
        breached: bool,
    ):
        self.limiter = ref(limiter)
        self.limit = limit
        self.request_args = request_args
        self.key = limit.key_for(*request_args)
        self.breached = breached
        self._window: Optional[Tuple[int, int]] = None

    @property
    def window(self):
        if not self._window:
            self._window = self.limiter().get_window_stats(
                self.limit, *self.request_args
            )

        return self._window

    @property
    def reset_at(self) -> int:
        """Timestamp at which the rate limit will be reset"""

        return int(self.window[0] + 1)

    @property
    def remaining(self) -> int:
        """Quantity remaining for this rate limit"""

        return self.window[1]


MAX_BACKEND_CHECKS = 5


class Limiter(object):
    """
    The :class:`Limiter` class initializes the Flask-Limiter extension.

    :param app: :class:`flask.Flask` instance to initialize the extension with.
    :param key_func: a callable that returns the domain to rate limit
      by.
    :param default_limits: a variable list of strings or callables
     returning strings denoting default limits to apply to all routes.
     :ref:`ratelimit-string` for  more details.
    :param default_limits_per_method: whether default limits are applied
     per method, per route or as a combination of all method per route.
    :param default_limits_exempt_when: a function that should return
     True/False to decide if the default limits should be skipped
    :param default_limits_deduct_when: a function that receives the
     current :class:`flask.Response` object and returns True/False to decide
     if a deduction should be made from the default rate limit(s)
    :param application_limits: a variable list of strings or callables
     returning strings for limits that are applied to the entire application
     (i.e a shared limit for all routes)
    :param headers_enabled: whether ``X-RateLimit`` response headers are
     written.
    :param header_name_mapping: Mapping of header names to use if
     :paramref:`Limiter.headers_enabled` is ``True``. If no mapping is provided
     the default values will be used.
    :param strategy: the strategy to use. Refer to :ref:`ratelimit-strategy`
    :param storage_uri: the storage location.
     Refer to :data:`RATELIMIT_STORAGE_URI`
    :param storage_options: kwargs to pass to the storage implementation
     upon instantiation.
    :param auto_check: whether to automatically check the rate limit in
     the before_request chain of the application. default ``True``
    :param swallow_errors: whether to swallow errors when hitting a rate
     limit. An exception will still be logged. default ``False``
    :param fail_on_first_breach: whether to stop processing remaining limits
     after the first breach. default ``True``
    :param in_memory_fallback: a variable list of strings or callables
     returning strings denoting fallback limits to apply when the storage is
     down.
    :param in_memory_fallback_enabled: fall back to in memory
     storage when the main storage is down and inherits the original limits.
     default ``False``
    :param retry_after: Allows configuration of how the value of the
     `Retry-After` header is rendered. One of `http-date` or `delta-seconds`.
    :param key_prefix: prefix prepended to rate limiter keys and app context global names.
    :param enabled: Whether the extension is enabled or not
    """

    def __init__(
        self,
        app: Optional[Flask] = None,
        key_func: Callable[[], str] = None,
        default_limits: List[Union[str, Callable[[], str]]] = [],
        default_limits_per_method: bool = None,
        default_limits_exempt_when: Callable[[], bool] = None,
        default_limits_deduct_when: Callable[[], bool] = None,
        application_limits: List[Union[str, Callable[[], str]]] = [],
        headers_enabled: bool = None,
        header_name_mapping: Dict[HEADERS, str] = {},
        strategy: Optional[str] = None,
        storage_uri: Optional[str] = None,
        storage_options={},
        auto_check: bool = True,
        swallow_errors: bool = None,
        fail_on_first_breach: bool = None,
        in_memory_fallback: List[str] = [],
        in_memory_fallback_enabled: bool = None,
        retry_after: str = None,
        key_prefix: str = "",
        enabled: bool = True,
    ):
        self.app = app
        self.logger = logging.getLogger("flask-limiter")

        self.enabled = enabled
        self.initialized = False
        self._default_limits = []
        self._default_limits_per_method = default_limits_per_method
        self._default_limits_exempt_when = default_limits_exempt_when
        self._default_limits_deduct_when = default_limits_deduct_when
        self._application_limits = []
        self._in_memory_fallback = []
        self._in_memory_fallback_enabled = (
            in_memory_fallback_enabled or len(in_memory_fallback) > 0
        )
        self._exempt_routes: Set[str] = set()
        self._request_filters: List[Callable[[], bool]] = []
        self._headers_enabled = headers_enabled
        self._header_mapping = header_name_mapping
        self._retry_after = retry_after
        self._strategy = strategy
        self._storage_uri = storage_uri
        self._storage_options = storage_options
        self._auto_check = auto_check
        self._swallow_errors = swallow_errors
        self._fail_on_first_breach = fail_on_first_breach

        # No longer optional
        assert key_func

        self._key_func = key_func
        self._key_prefix = key_prefix

        for limit in default_limits:
            self._default_limits.extend(
                [
                    LimitGroup(
                        limit,
                        self._key_func,
                        None,
                        False,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        1,
                    )
                ]
            )

        for limit in application_limits:
            self._application_limits.extend(
                [
                    LimitGroup(
                        limit,
                        self._key_func,
                        "global",
                        False,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        1,
                    )
                ]
            )

        for limit in in_memory_fallback:
            self._in_memory_fallback.extend(
                [
                    LimitGroup(
                        limit,
                        self._key_func,
                        None,
                        False,
                        None,
                        None,
                        None,
                        None,
                        None,
                        None,
                        1,
                    )
                ]
            )
        self._route_limits: Dict[str, List[Limit]] = {}
        self._dynamic_route_limits: Dict[str, List[LimitGroup]] = {}
        self._blueprint_limits: Dict[str, List[Limit]] = {}
        self._blueprint_dynamic_limits: Dict[str, List[LimitGroup]] = {}
        self._blueprint_exempt: Set[str] = set()
        self._storage: Optional[Storage] = None
        self._limiter: Optional[RateLimiter] = None
        self._storage_dead = False
        self._fallback_limiter: Optional[RateLimiter] = None
        self.__check_backend_count = 0
        self.__last_check_backend = time.time()
        self.__marked_for_limiting: Dict[str, List[str]] = {}

        class BlackHoleHandler(logging.StreamHandler):
            def emit(*_):
                return

        self.logger.addHandler(BlackHoleHandler())

        if app:
            self.init_app(app)

    def init_app(self, app: Flask):
        """
        :param app: :class:`flask.Flask` instance to rate limit.
        """
        config = app.config
        self.enabled = config.setdefault(C.ENABLED, self.enabled)

        if not self.enabled:
            return

        if self._default_limits_per_method is None:
            self._default_limits_per_method = config.get(
                C.DEFAULT_LIMITS_PER_METHOD, False
            )
        self._default_limits_exempt_when = (
            self._default_limits_exempt_when or config.get(C.DEFAULT_LIMITS_EXEMPT_WHEN)
        )
        self._default_limits_deduct_when = (
            self._default_limits_deduct_when or config.get(C.DEFAULT_LIMITS_DEDUCT_WHEN)
        )

        if self._swallow_errors is None:
            self._swallow_errors = config.get(C.SWALLOW_ERRORS, False)

        if self._fail_on_first_breach is None:
            self._fail_on_first_breach = config.get(C.FAIL_ON_FIRST_BREACH, True)

        if self._headers_enabled is None:
            self._headers_enabled = config.get(C.HEADERS_ENABLED, False)

        self._storage_options.update(config.get(C.STORAGE_OPTIONS, {}))
        storage_uri_from_config = config.get(
            C.STORAGE_URI, config.get(C.STORAGE_URL, "memory://")
        )
        self._storage = cast(
            Storage,
            storage_from_string(
                self._storage_uri or storage_uri_from_config, **self._storage_options
            ),
        )
        strategy = self._strategy or config.setdefault(C.STRATEGY, "fixed-window")

        if strategy not in STRATEGIES:
            raise ConfigurationError("Invalid rate limiting strategy %s" % strategy)
        self._limiter = STRATEGIES[strategy](self._storage)

        self._header_mapping = {
            HEADERS.RESET: self._header_mapping.get(
                HEADERS.RESET, config.get(C.HEADER_RESET, HEADERS.RESET.value)
            ),
            HEADERS.REMAINING: self._header_mapping.get(
                HEADERS.REMAINING,
                config.get(C.HEADER_REMAINING, HEADERS.REMAINING.value),
            ),
            HEADERS.LIMIT: self._header_mapping.get(
                HEADERS.LIMIT, config.get(C.HEADER_LIMIT, HEADERS.LIMIT.value)
            ),
            HEADERS.RETRY_AFTER: self._header_mapping.get(
                HEADERS.RETRY_AFTER,
                config.get(C.HEADER_RETRY_AFTER, HEADERS.RETRY_AFTER.value),
            ),
        }
        self._retry_after = self._retry_after or config.get(C.HEADER_RETRY_AFTER_VALUE)

        self._key_prefix = self._key_prefix or config.get(C.KEY_PREFIX)

        app_limits = config.get(C.APPLICATION_LIMITS, None)

        if not self._application_limits and app_limits:
            self._application_limits = [
                LimitGroup(
                    app_limits,
                    self._key_func,
                    "global",
                    False,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    1,
                )
            ]

        conf_limits = config.get(C.DEFAULT_LIMITS, None)

        if not self._default_limits and conf_limits:
            self._default_limits = [
                LimitGroup(
                    conf_limits,
                    self._key_func,
                    None,
                    False,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    1,
                )
            ]

        for limit in self._default_limits:
            limit.per_method = self._default_limits_per_method
            limit.exempt_when = self._default_limits_exempt_when
            limit.deduct_when = self._default_limits_deduct_when

        self.__configure_fallbacks(app, strategy)

        # purely for backward compatibility as stated in flask documentation

        if not hasattr(app, "extensions"):
            app.extensions = {}  # pragma: no cover

        if not app.extensions.get("limiter"):
            if self._auto_check:
                app.before_request(self.__check_request_limit)
            app.after_request(self.__inject_headers)

        app.extensions["limiter"] = self
        self.initialized = True

    def limit(
        self,
        limit_value: Union[str, Callable[[], str]],
        key_func: Callable[[], str] = None,
        per_method: bool = False,
        methods: List[str] = None,
        error_message: str = None,
        exempt_when: Callable[[], bool] = None,
        override_defaults: bool = True,
        deduct_when: Callable[[Response], bool] = None,
        on_breach: Callable[[RequestLimit], None] = None,
        cost: int = 1,
    ) -> Callable:
        """
        decorator to be used for rate limiting individual routes or blueprints.

        :param limit_value: rate limit string or a callable that returns a
         string. :ref:`ratelimit-string` for more details.
        :param key_func: function/lambda to extract the unique
         identifier for the rate limit. defaults to remote address of the
         request.
        :param per_method: whether the limit is sub categorized into the
         http method of the request.
        :param methods: if specified, only the methods in this list will
         be rate limited (default: None).
        :param error_message: string (or callable that returns one) to override
         the error message used in the response.
        :param exempt_when: function/lambda used to decide if the rate
         limit should skipped.
        :param override_defaults:  whether the decorated limit overrides
         the default limits. (default: True)
        :param deduct_when: a function that receives the current
         :class:`flask.Response` object and returns True/False to decide if a
         deduction should be done from the rate limit
        :param on_breach: a function that will be called when this limit
         is breached.
        :param cost: cost of a hit (default: 1).
        """

        return self.__limit_decorator(
            limit_value,
            key_func,
            per_method=per_method,
            methods=methods,
            error_message=error_message,
            exempt_when=exempt_when,
            override_defaults=override_defaults,
            deduct_when=deduct_when,
            on_breach=on_breach,
            cost=cost,
        )

    def shared_limit(
        self,
        limit_value: Union[str, Callable[[], str]],
        scope: Union[str, Callable[[], str]],
        key_func: Callable[[], str] = None,
        error_message: str = None,
        exempt_when: Callable[[], bool] = None,
        override_defaults=True,
        deduct_when: Callable[[Response], bool] = None,
        on_breach: Callable[[RequestLimit], None] = None,
        cost: int = 1,
    ) -> Callable:
        """
        decorator to be applied to multiple routes sharing the same rate limit.

        :param limit_value: rate limit string or a callable that returns a
         string. :ref:`ratelimit-string` for more details.
        :param scope: a string or callable that returns a string
         for defining the rate limiting scope.
        :param key_func: function/lambda to extract the unique
         identifier for the rate limit. defaults to remote address of the
         request.
        :param error_message: string (or callable that returns one) to override
         the error message used in the response.
        :param function exempt_when: function/lambda used to decide if the rate
         limit should skipped.
        :param override_defaults:  whether the decorated limit overrides
         the default limits. (default: True)
        :param deduct_when: a function that receives the current
         :class:`flask.Response`  object and returns True/False to decide if a
         deduction should be done from the rate limit
        :param on_breach: a function that will be called when this limit
         is breached.
        :param cost: cost of a hit (default: 1).
        """

        return self.__limit_decorator(
            limit_value,
            key_func,
            True,
            scope,
            error_message=error_message,
            exempt_when=exempt_when,
            override_defaults=override_defaults,
            deduct_when=deduct_when,
            on_breach=on_breach,
            cost=cost,
        )

    def exempt(self, obj: Union[Callable, Blueprint]):
        """
        decorator to mark a view or all views in a blueprint as exempt from
        rate limits.

        :param obj: view or blueprint to mark as exempt.
        """

        if isinstance(obj, Blueprint):
            self._blueprint_exempt.add(obj.name)
        else:
            self._exempt_routes.add(f"{obj.__module__}.{obj.__name__}")

            return obj

    def request_filter(self, fn: Callable[[], bool]) -> Callable:
        """
        decorator to mark a function as a filter to be executed
        to check if the request is exempt from rate limiting.

        :param fn: The function will be called before evaluating any rate limits
         to decide whether to perform rate limit or skip it.
        """
        self._request_filters.append(fn)

        return fn

    def __configure_fallbacks(self, app, strategy):
        config = app.config
        fallback_enabled = config.get(C.IN_MEMORY_FALLBACK_ENABLED, False)
        fallback_limits = config.get(C.IN_MEMORY_FALLBACK, None)

        if not self._in_memory_fallback and fallback_limits:
            self._in_memory_fallback = [
                LimitGroup(
                    fallback_limits,
                    self._key_func,
                    None,
                    False,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    1,
                )
            ]

        if not self._in_memory_fallback_enabled:
            self._in_memory_fallback_enabled = (
                fallback_enabled or len(self._in_memory_fallback) > 0
            )

        if self._in_memory_fallback_enabled:
            self._fallback_storage = MemoryStorage()
            self._fallback_limiter = STRATEGIES[strategy](self._fallback_storage)

    def __should_check_backend(self):
        if self.__check_backend_count > MAX_BACKEND_CHECKS:
            self.__check_backend_count = 0

        if time.time() - self.__last_check_backend > pow(2, self.__check_backend_count):
            self.__last_check_backend = time.time()
            self.__check_backend_count += 1

            return True

        return False

    def check(self) -> None:
        """
        check the limits for the current request

        :raises: RateLimitExceeded
        """
        self.__check_request_limit(False)

    def reset(self) -> None:
        """
        resets the storage if it supports being reset
        """
        try:
            self._storage.reset()
            self.logger.info("Storage has been reset and all limits cleared")
        except NotImplementedError:
            self.logger.warning("This storage type does not support being reset")

    @property
    def limiter(self) -> RateLimiter:
        if self._storage_dead and self._in_memory_fallback_enabled:
            return self._fallback_limiter
        else:
            return self._limiter

    @property
    def current_limit(self) -> Optional[RequestLimit]:
        """
        Get details for the most relevant rate limit used in this request.

        In a scenario where multiple rate limits are active for a single request
        and none are breached, the rate limit which applies to the smallest
        time window will be returned.

        .. important:: The value of ``remaining`` in :class:`RequestLimit` is after
           deduction for the current request.


        For example::

            @limit("1/second")
            @limit("60/minute")
            @limit("2/day")
            def route(...):
                ...

        - Request 1 at ``t=0`` (no breach): this will return the details for for ``1/second``
        - Request 2 at ``t=1`` (no breach): it will still return the details for ``1/second``
        - Request 3 at ``t=2`` (breach): it will return the details for ``2/day``
        """
        last_limit = getattr(g, f"{self._key_prefix}_view_rate_limit", None)
        breached_limits = getattr(g, f"{self._key_prefix}_breached_limits", [])

        if last_limit:
            return RequestLimit(
                limit=last_limit[0],
                limiter=self.limiter,
                request_args=last_limit[1:],
                breached=last_limit[0] in breached_limits,
            )

        return None

    @property
    def current_limits(self) -> List[RequestLimit]:
        """
        Get a list of all rate limits that were applicable and evaluated
        within the context of this request.

        The limits are returned in a sorted order by smallest window size first.
        """
        all_limits = getattr(g, f"{self._key_prefix}_view_rate_limits", [])
        breached_limits = getattr(g, f"{self._key_prefix}_breached_limits", [])

        return list(
            RequestLimit(
                limit=limit[0],
                limiter=self.limiter,
                request_args=limit[1:],
                breached=limit[0] in breached_limits,
            )
            for limit in sorted(all_limits)
        )

    def __check_conditional_deductions(self, response):

        for lim, args in getattr(
            g, f"{self._key_prefix}_conditional_deductions", {}
        ).items():
            if lim.deduct_when(response):
                self.limiter.hit(lim.limit, *args, cost=lim.cost)

        return response

    def __inject_headers(self, response):
        self.__check_conditional_deductions(response)
        header_limit = self.current_limit

        if self.enabled and self._headers_enabled and header_limit:
            try:
                reset_at = header_limit.reset_at
                response.headers.add(
                    self._header_mapping[HEADERS.LIMIT],
                    str(header_limit.limit.amount),
                )
                response.headers.add(
                    self._header_mapping[HEADERS.REMAINING], header_limit.remaining
                )
                response.headers.add(self._header_mapping[HEADERS.RESET], reset_at)

                # response may have an existing retry after
                existing_retry_after_header = response.headers.get("Retry-After")

                if existing_retry_after_header is not None:
                    # might be in http-date format
                    retry_after: Union[float, datetime.datetime] = parse_date(
                        existing_retry_after_header
                    )

                    # parse_date failure returns None

                    if retry_after is None:
                        retry_after = time.time() + int(existing_retry_after_header)

                    if isinstance(retry_after, datetime.datetime):
                        retry_after = time.mktime(retry_after.timetuple())

                    reset_at = max(int(retry_after), reset_at)

                # set the header instead of using add
                response.headers.set(
                    self._header_mapping[HEADERS.RETRY_AFTER],
                    self._retry_after == "http-date"
                    and http_date(reset_at)
                    or int(reset_at - time.time()),
                )
            except Exception as e:  # noqa: E722
                if self._in_memory_fallback_enabled and not self._storage_dead:
                    self.logger.warning(
                        "Rate limit storage unreachable - falling back to"
                        " in-memory storage"
                    )
                    self._storage_dead = True
                    response = self.__inject_headers(response)
                else:
                    if self._swallow_errors:
                        self.logger.exception(
                            "Failed to update rate limit headers. " "Swallowing error"
                        )
                    else:
                        raise e

        return response

    def __evaluate_limits(self, endpoint, limits):
        failed_limits = []
        limit_for_header = None
        view_limits = []

        if not getattr(g, "%s_conditional_deductions" % self._key_prefix, None):
            setattr(g, "%s_conditional_deductions" % self._key_prefix, {})

        for lim in sorted(limits, key=lambda x: x.limit):
            limit_scope = lim.scope or endpoint

            if lim.is_exempt or lim.method_exempt:
                continue

            if lim.per_method:
                limit_scope += ":%s" % request.method
            limit_key = lim.key_func()
            args = [limit_key, limit_scope]
            kwargs = {}

            if not all(args):
                self.logger.error(
                    "Skipping limit: %s. Empty value found in parameters.", lim.limit
                )

                continue

            if self._key_prefix:
                args = [self._key_prefix] + args

            if lim.deduct_when:
                getattr(g, "%s_conditional_deductions" % self._key_prefix)[lim] = args
                method = self.limiter.test
            else:
                method = self.limiter.hit
                kwargs["cost"] = lim.cost

            if not limit_for_header or lim.limit < limit_for_header[0]:
                limit_for_header = [lim.limit] + args

            view_limits.append([lim.limit] + args)

            if not method(lim.limit, *args, **kwargs):
                self.logger.warning(
                    "ratelimit %s (%s) exceeded at endpoint: %s",
                    lim.limit,
                    limit_key,
                    limit_scope,
                )
                failed_limits.append([lim, args])
                limit_for_header = [lim.limit] + args

                if self._fail_on_first_breach:
                    break

        setattr(g, f"{self._key_prefix}_view_rate_limit", limit_for_header)
        setattr(g, f"{self._key_prefix}_view_rate_limits", view_limits)

        if failed_limits:
            inner_limits = [l[0] for l in failed_limits]

            for limit in failed_limits:
                if limit[0].on_breach:
                    try:
                        limit[0].on_breach(
                            RequestLimit(
                                self.limiter,
                                limit=limit[0].limit,
                                request_args=limit[1:],
                                breached=True,
                            )
                        )
                    except Exception:  # noqa
                        self.logger.warning("on_breach callback failed")

            setattr(
                g,
                f"{self._key_prefix}_breached_limits",
                [limit.limit for limit in inner_limits],
            )
            raise RateLimitExceeded(sorted(inner_limits)[0])

    def __check_request_limit(self, in_middleware=True):
        endpoint = request.endpoint or ""
        view_func = current_app.view_functions.get(endpoint, None)
        name = f"{view_func.__module__}.{view_func.__name__}" if view_func else ""

        if (
            not request.endpoint
            or not (self.enabled and self.initialized)
            or request.endpoint == "static"
            or name in self._exempt_routes
            or request.blueprint in self._blueprint_exempt
            or any(fn() for fn in self._request_filters)
            or g.get(f"{self._key_prefix}_rate_limiting_complete")
        ):
            return
        limits: List[Limit] = []
        dynamic_limits: List[Limit] = []

        if not in_middleware:
            limits = name in self._route_limits and self._route_limits[name] or []
            dynamic_limits = []

            if name in self._dynamic_route_limits:
                for lim in self._dynamic_route_limits[name]:
                    try:
                        dynamic_limits.extend(list(lim))
                    except ValueError as e:
                        self.logger.error(
                            "failed to load ratelimit for " "view function %s (%s)",
                            name,
                            e,
                        )

        if request.blueprint:
            if (
                request.blueprint in self._blueprint_dynamic_limits
                and not dynamic_limits
            ):
                for limit_group in self._blueprint_dynamic_limits[request.blueprint]:
                    try:
                        dynamic_limits.extend(
                            [
                                Limit(
                                    limit.limit,
                                    limit.key_func,
                                    limit.scope,
                                    limit.per_method,
                                    limit.methods,
                                    limit.error_message,
                                    limit.exempt_when,
                                    limit.override_defaults,
                                    limit.deduct_when,
                                    limit.on_breach,
                                    limit.cost,
                                )
                                for limit in limit_group
                            ]
                        )
                    except ValueError as e:
                        self.logger.error(
                            "failed to load ratelimit for blueprint %s (%s)",
                            request.blueprint,
                            e,
                        )

            if request.blueprint in self._blueprint_limits and not limits:
                limits.extend(self._blueprint_limits[request.blueprint])

        try:
            all_limits = []

            if self._storage_dead and self._fallback_limiter:
                if in_middleware and name in self.__marked_for_limiting:
                    pass
                else:
                    if self.__should_check_backend() and self._storage.check():
                        self.logger.info("Rate limit storage recovered")
                        self._storage_dead = False
                        self.__check_backend_count = 0
                    else:
                        all_limits = list(itertools.chain(*self._in_memory_fallback))

            if not all_limits:
                route_limits = limits + dynamic_limits
                all_limits = (
                    list(itertools.chain(*self._application_limits))
                    if in_middleware
                    else []
                )
                all_limits += route_limits
                explicit_limits_exempt = all(
                    limit.method_exempt for limit in route_limits
                )
                combined_defaults = all(
                    not limit.override_defaults for limit in route_limits
                )
                before_request_context = (
                    in_middleware and name in self.__marked_for_limiting
                )

                if (
                    explicit_limits_exempt or combined_defaults
                ) and not before_request_context:
                    all_limits += list(itertools.chain(*self._default_limits))
            self.__evaluate_limits(endpoint, all_limits)
        except Exception as e:
            if isinstance(e, RateLimitExceeded):
                raise e

            if self._in_memory_fallback_enabled and not self._storage_dead:
                self.logger.warning(
                    "Rate limit storage unreachable - falling back to"
                    " in-memory storage"
                )
                self._storage_dead = True
                self.__check_request_limit(in_middleware)
            else:
                if self._swallow_errors:
                    self.logger.exception("Failed to rate limit. Swallowing error")
                else:
                    raise e

    def __limit_decorator(
        self,
        limit_value,
        key_func=None,
        shared=False,
        scope=None,
        per_method=False,
        methods=None,
        error_message=None,
        exempt_when=None,
        override_defaults=True,
        deduct_when=None,
        on_breach=None,
        cost=1,
    ):
        _scope = scope if shared else None

        def _inner(obj):
            func = key_func or self._key_func
            is_route = not isinstance(obj, Blueprint)
            name = f"{obj.__module__}.{obj.__name__}" if is_route else obj.name
            dynamic_limit, static_limits = None, []

            if callable(limit_value):
                dynamic_limit = LimitGroup(
                    limit_value,
                    func,
                    _scope,
                    per_method,
                    methods,
                    error_message,
                    exempt_when,
                    override_defaults,
                    deduct_when,
                    on_breach,
                    cost,
                )
            else:
                try:
                    static_limits = list(
                        LimitGroup(
                            limit_value,
                            func,
                            _scope,
                            per_method,
                            methods,
                            error_message,
                            exempt_when,
                            override_defaults,
                            deduct_when,
                            on_breach,
                            cost,
                        )
                    )
                except ValueError as e:
                    self.logger.error(
                        "failed to configure %s %s (%s)",
                        "view function" if is_route else "blueprint",
                        name,
                        e,
                    )

            if isinstance(obj, Blueprint):
                if dynamic_limit:
                    self._blueprint_dynamic_limits.setdefault(name, []).append(
                        dynamic_limit
                    )
                else:
                    self._blueprint_limits.setdefault(name, []).extend(static_limits)
            else:
                self.__marked_for_limiting.setdefault(name, []).append(obj)

                if dynamic_limit:
                    self._dynamic_route_limits.setdefault(name, []).append(
                        dynamic_limit
                    )
                else:
                    self._route_limits.setdefault(name, []).extend(static_limits)

                @wraps(obj)
                def __inner(*a, **k):
                    if self._auto_check and not g.get(
                        f"{self._key_prefix}_rate_limiting_complete"
                    ):
                        self.__check_request_limit(False)
                        setattr(g, f"{self._key_prefix}_rate_limiting_complete", True)

                    return current_app.ensure_sync(obj)(*a, **k)

                return __inner

        return _inner
