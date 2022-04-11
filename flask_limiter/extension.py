"""
Flask-Limiter Extension
"""
import datetime
import itertools
import logging
import time
from collections import defaultdict
from functools import wraps
from typing import Callable, Dict, List, Optional, Tuple, Union, cast

from flask import Blueprint, Flask, Response, _request_ctx_stack, current_app, request
from limits import RateLimitItem
from limits.errors import ConfigurationError
from limits.storage import MemoryStorage, Storage, storage_from_string
from limits.strategies import STRATEGIES, RateLimiter
from werkzeug.http import http_date, parse_date

from .constants import MAX_BACKEND_CHECKS, ConfigVars, ExemptionScope, HeaderNames
from .errors import RateLimitExceeded
from .manager import LimitManager
from .wrappers import Limit, LimitGroup


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
        self.limiter = limiter
        self.limit = limit
        self.request_args = request_args
        self.key = limit.key_for(*request_args)
        self.breached = breached
        self._window: Optional[Tuple[int, int]] = None

    @property
    def window(self):
        if not self._window:
            self._window = self.limiter.get_window_stats(self.limit, *self.request_args)

        return self._window

    @property
    def reset_at(self) -> int:
        """Timestamp at which the rate limit will be reset"""

        return int(self.window[0] + 1)

    @property
    def remaining(self) -> int:
        """Quantity remaining for this rate limit"""

        return self.window[1]


class Limiter:
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
    :param on_breach: a function that will be called when any limit in this
     extension is breached.
    :param on_breach: whether to stop processing remaining limits
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
        header_name_mapping: Dict[HeaderNames, str] = {},
        strategy: Optional[str] = None,
        storage_uri: Optional[str] = None,
        storage_options={},
        auto_check: bool = True,
        swallow_errors: bool = None,
        fail_on_first_breach: bool = None,
        on_breach: Callable[[RequestLimit], None] = None,
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
        self._default_limits_per_method = default_limits_per_method
        self._default_limits_exempt_when = default_limits_exempt_when
        self._default_limits_deduct_when = default_limits_deduct_when
        self._in_memory_fallback = []
        self._in_memory_fallback_enabled = (
            in_memory_fallback_enabled or len(in_memory_fallback) > 0
        )
        self._route_exemptions: Dict[str, ExemptionScope] = defaultdict(
            lambda: ExemptionScope.NONE
        )
        self._blueprint_exemptions: Dict[str, ExemptionScope] = defaultdict(
            lambda: ExemptionScope.NONE
        )
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
        self._on_breach = on_breach

        # No longer optional
        assert key_func

        self._key_func = key_func
        self._key_prefix = key_prefix

        _default_limits = [
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
            for limit in default_limits
        ]

        _application_limits = [
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
            for limit in application_limits
        ]

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

        self.limit_manager = LimitManager(
            application_limits=_application_limits,
            default_limits=_default_limits,
            static_route_limits={},
            dynamic_route_limits={},
            static_blueprint_limits={},
            dynamic_blueprint_limits={},
            route_exemptions=self._route_exemptions,
            blueprint_exemptions=self._blueprint_exemptions,
        )

        if app:
            self.init_app(app)

    def init_app(self, app: Flask):
        """
        :param app: :class:`flask.Flask` instance to rate limit.
        """
        config = app.config
        self.enabled = config.setdefault(ConfigVars.ENABLED, self.enabled)

        if not self.enabled:
            return

        if self._default_limits_per_method is None:
            self._default_limits_per_method = config.get(
                ConfigVars.DEFAULT_LIMITS_PER_METHOD, False
            )
        self._default_limits_exempt_when = (
            self._default_limits_exempt_when
            or config.get(ConfigVars.DEFAULT_LIMITS_EXEMPT_WHEN)
        )
        self._default_limits_deduct_when = (
            self._default_limits_deduct_when
            or config.get(ConfigVars.DEFAULT_LIMITS_DEDUCT_WHEN)
        )

        if self._swallow_errors is None:
            self._swallow_errors = config.get(ConfigVars.SWALLOW_ERRORS, False)

        if self._fail_on_first_breach is None:
            self._fail_on_first_breach = config.get(
                ConfigVars.FAIL_ON_FIRST_BREACH, True
            )

        if self._headers_enabled is None:
            self._headers_enabled = config.get(ConfigVars.HEADERS_ENABLED, False)

        self._storage_options.update(config.get(ConfigVars.STORAGE_OPTIONS, {}))
        storage_uri_from_config = config.get(
            ConfigVars.STORAGE_URI, config.get(ConfigVars.STORAGE_URL, "memory://")
        )
        self._storage = cast(
            Storage,
            storage_from_string(
                self._storage_uri or storage_uri_from_config, **self._storage_options
            ),
        )
        strategy = self._strategy or config.setdefault(
            ConfigVars.STRATEGY, "fixed-window"
        )

        if strategy not in STRATEGIES:
            raise ConfigurationError("Invalid rate limiting strategy %s" % strategy)
        self._limiter = STRATEGIES[strategy](self._storage)

        self._header_mapping = {
            HeaderNames.RESET: self._header_mapping.get(
                HeaderNames.RESET,
                config.get(ConfigVars.HEADER_RESET, HeaderNames.RESET.value),
            ),
            HeaderNames.REMAINING: self._header_mapping.get(
                HeaderNames.REMAINING,
                config.get(ConfigVars.HEADER_REMAINING, HeaderNames.REMAINING.value),
            ),
            HeaderNames.LIMIT: self._header_mapping.get(
                HeaderNames.LIMIT,
                config.get(ConfigVars.HEADER_LIMIT, HeaderNames.LIMIT.value),
            ),
            HeaderNames.RETRY_AFTER: self._header_mapping.get(
                HeaderNames.RETRY_AFTER,
                config.get(
                    ConfigVars.HEADER_RETRY_AFTER, HeaderNames.RETRY_AFTER.value
                ),
            ),
        }
        self._retry_after = self._retry_after or config.get(
            ConfigVars.HEADER_RETRY_AFTER_VALUE
        )

        self._key_prefix = self._key_prefix or config.get(ConfigVars.KEY_PREFIX, "")

        app_limits = config.get(ConfigVars.APPLICATION_LIMITS, None)

        if not self.limit_manager.application_limits and app_limits:
            self.limit_manager.set_application_limits(
                [
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
            )
        conf_limits = config.get(ConfigVars.DEFAULT_LIMITS, None)

        if not self.limit_manager.default_limits and conf_limits:
            self.limit_manager.set_default_limits(
                [
                    LimitGroup(
                        conf_limits,
                        self._key_func,
                        None,
                        self._default_limits_per_method,
                        None,
                        None,
                        self._default_limits_exempt_when,
                        None,
                        self._default_limits_deduct_when,
                        None,
                        1,
                    )
                ]
            )
        else:
            # This is dumb but just keeping it since it is existing behavior.
            default_limit_groups = self.limit_manager._default_limits
            for group in default_limit_groups:
                group.per_method = self._default_limits_per_method
                group.exempt_when = self._default_limits_exempt_when
                group.deduct_when = self._default_limits_deduct_when
            self.limit_manager.set_default_limits(default_limit_groups)

        self.__configure_fallbacks(app, strategy)

        # purely for backward compatibility as stated in flask documentation
        if not hasattr(app, "extensions"):
            app.extensions = {}  # pragma: no cover

        if not app.extensions.get("limiter"):
            if self._auto_check:
                app.before_request(self.__check_request_limit)
            app.after_request(self.__inject_headers)
            app.teardown_request(self.__release_context)

        app.extensions["limiter"] = self
        self.initialized = True

    @property
    def context(self):
        ctx = _request_ctx_stack.top
        if ctx is not None:
            if not hasattr(ctx, "_limiter_request_context"):
                ctx._limiter_request_context = {}
            return ctx._limiter_request_context

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
        cost: Union[int, Callable[[], int]] = 1,
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
         be rate limited (default: ``None``).
        :param error_message: string (or callable that returns one) to override
         the error message used in the response.
        :param exempt_when: function/lambda used to decide if the rate
         limit should skipped.
        :param override_defaults:  whether the decorated limit overrides
         the default limits (Default: ``True``).

         .. note:: When used with a :class:`~flask.Blueprint` the meaning
            of the parameter extends to any parents the blueprint instance is
            registered under. For more details see :ref:`recipes:nested blueprints`

        :param deduct_when: a function that receives the current
         :class:`flask.Response` object and returns True/False to decide if a
         deduction should be done from the rate limit
        :param on_breach: a function that will be called when this limit
         is breached.
        :param cost: The cost of a hit or a function that
         takes no parameters and returns the cost as an integer (Default: ``1``).
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
        cost: Union[int, Callable[[], int]] = 1,
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
        :param override_defaults: whether the decorated limit overrides
         the default limits. (default: ``True``)

         .. note:: When used with a :class:`~flask.Blueprint` the meaning
            of the parameter extends to any parents the blueprint instance is
            registered under. For more details see :ref:`recipes:nested blueprints`
        :param deduct_when: a function that receives the current
         :class:`flask.Response`  object and returns True/False to decide if a
         deduction should be done from the rate limit
        :param on_breach: a function that will be called when this limit
         is breached.
        :param cost: The cost of a hit or a function that
         takes no parameters and returns the cost as an integer (default: ``1``).
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

    def exempt(
        self,
        obj: Union[Callable, Blueprint],
        flags: ExemptionScope = ExemptionScope.APPLICATION | ExemptionScope.DEFAULT,
    ):
        """
        decorator to mark a view or all views in a blueprint as exempt from
        rate limits.

        :param obj: view or blueprint to mark as exempt.
        :param flags: Controls the scope of the exemption. By default
         application wide limits and defaults configured on the extension
         are opted out of. Additional flags can be used to control the behavior
         when :paramref:`obj` is a Blueprint that is nested under another Blueprint
         or has other Blueprints nested under it (See :ref:`recipes:nested blueprints`)
        """

        if isinstance(obj, Blueprint):
            self.limit_manager.add_blueprint_exemption(obj.name, flags)
        else:
            self.limit_manager.add_route_exemption(
                f"{obj.__module__}.{obj.__name__}", flags
            )
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
        fallback_enabled = config.get(ConfigVars.IN_MEMORY_FALLBACK_ENABLED, False)
        fallback_limits = config.get(ConfigVars.IN_MEMORY_FALLBACK, None)

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
        last_limit = self.context.get(f"{self._key_prefix}_view_rate_limit", None)
        breached_limits = self.context.get(f"{self._key_prefix}_breached_limits", [])

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
        all_limits = self.context.get(f"{self._key_prefix}_view_rate_limits", [])
        breached_limits = self.context.get(f"{self._key_prefix}_breached_limits", [])

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

        for lim, args in self.context.get(
            f"{self._key_prefix}_conditional_deductions", {}
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
                    self._header_mapping[HeaderNames.LIMIT],
                    str(header_limit.limit.amount),
                )
                response.headers.add(
                    self._header_mapping[HeaderNames.REMAINING], header_limit.remaining
                )
                response.headers.add(self._header_mapping[HeaderNames.RESET], reset_at)

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
                    self._header_mapping[HeaderNames.RETRY_AFTER],
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

    def __check_all_limits_exempt(self, request) -> bool:
        return (
            not request.endpoint
            or not (self.enabled and self.initialized)
            or request.endpoint == "static"
            or any(fn() for fn in self._request_filters)
            or self.context.get(f"{self._key_prefix}_rate_limiting_complete")
        )

    def __filter_limits(self, request, in_middleware: bool = False) -> List[Limit]:
        endpoint = request.endpoint or ""
        view_func = current_app.view_functions.get(endpoint, None)
        name = f"{view_func.__module__}.{view_func.__name__}" if view_func else ""

        if self.__check_all_limits_exempt(request):
            return []

        route_limits: List[Limit] = []

        before_request_context = in_middleware and name in self.__marked_for_limiting

        if not in_middleware:
            route_limits.extend(self.limit_manager.route_limits(request))

        if request.blueprint:
            if not before_request_context and (
                not route_limits
                or all(not limit.override_defaults for limit in route_limits)
            ):
                route_limits.extend(self.limit_manager.blueprint_limits(request))

        exemption_scope = self.limit_manager.exemption_scope(request)
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
            all_limits = (
                self.limit_manager.application_limits
                if in_middleware and not (exemption_scope & ExemptionScope.APPLICATION)
                else []
            )
            all_limits += route_limits
            explicit_limits_exempt = all(limit.method_exempt for limit in route_limits)
            combined_defaults = all(
                not limit.override_defaults for limit in route_limits
            )

            if (explicit_limits_exempt or combined_defaults) and not (
                before_request_context or exemption_scope & ExemptionScope.DEFAULT
            ):
                all_limits += self.limit_manager.default_limits
        return all_limits

    def __evaluate_limits(self, endpoint, limits):
        failed_limits = []
        limit_for_header = None
        view_limits = []
        if not self.context.get(f"{self._key_prefix}_conditional_deductions"):
            self.context["%s_conditional_deductions" % self._key_prefix] = {}

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
                self.context.get(f"{self._key_prefix}_conditional_deductions")[
                    lim
                ] = args
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

        self.context[f"{self._key_prefix}_view_rate_limit"] = limit_for_header
        self.context[f"{self._key_prefix}_view_rate_limits"] = view_limits

        if failed_limits:
            inner_limits = [limit[0] for limit in failed_limits]
            for limit in failed_limits:
                for cb in {self._on_breach, limit[0].on_breach}:
                    if cb:
                        try:
                            cb(
                                RequestLimit(
                                    self.limiter,
                                    limit=limit[0].limit,
                                    request_args=limit[1],
                                    breached=True,
                                )
                            )
                        except Exception:  # noqa
                            self.logger.warning("on_breach callback failed")

            self.context[f"{self._key_prefix}_breached_limits"] = [
                limit.limit for limit in inner_limits
            ]

            raise RateLimitExceeded(sorted(inner_limits)[0])

    def __check_request_limit(self, in_middleware=True):
        endpoint = request.endpoint or ""
        try:
            all_limits = self.__filter_limits(request, in_middleware)
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

    def __release_context(self, _):
        if self.context:
            self.context.clear()

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
                    self.limit_manager.add_runtime_blueprint_limits(name, dynamic_limit)
                else:
                    self.limit_manager.add_static_blueprint_limits(name, *static_limits)
            else:
                self.__marked_for_limiting.setdefault(name, []).append(obj)

                if dynamic_limit:
                    self.limit_manager.add_runtime_route_limits(name, dynamic_limit)
                else:
                    self.limit_manager.add_static_route_limits(name, *static_limits)

                @wraps(obj)
                def __inner(*a, **k):
                    if self._auto_check and not self.context.get(
                        f"{self._key_prefix}_rate_limiting_complete"
                    ):
                        self.__check_request_limit(False)
                        self.context[
                            f"{self._key_prefix}_rate_limiting_complete"
                        ] = True
                    return current_app.ensure_sync(obj)(*a, **k)

                return __inner

        return _inner
