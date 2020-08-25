"""
the flask extension
"""
import datetime
import itertools
import logging
import sys
import time
import warnings
from functools import wraps

import six
from flask import request, current_app, g, Blueprint
from limits.errors import ConfigurationError
from limits.storage import storage_from_string, MemoryStorage
from limits.strategies import STRATEGIES
from werkzeug.http import http_date, parse_date

from flask_limiter.wrappers import Limit, LimitGroup
from .errors import RateLimitExceeded
from .util import get_ipaddr


class C:
    ENABLED = "RATELIMIT_ENABLED"
    HEADERS_ENABLED = "RATELIMIT_HEADERS_ENABLED"
    STORAGE_URL = "RATELIMIT_STORAGE_URL"
    STORAGE_OPTIONS = "RATELIMIT_STORAGE_OPTIONS"
    STRATEGY = "RATELIMIT_STRATEGY"
    GLOBAL_LIMITS = "RATELIMIT_GLOBAL"
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


class HEADERS:
    RESET = 1
    REMAINING = 2
    LIMIT = 3
    RETRY_AFTER = 4


MAX_BACKEND_CHECKS = 5


class Limiter(object):
    """
    The :class:`Limiter` class initializes the Flask-Limiter extension.

    :param app: :class:`flask.Flask` instance to initialize the extension with.
    :param list default_limits: a variable list of strings or callables
     returning strings denoting global limits to apply to all routes.
     :ref:`ratelimit-string` for  more details.
    :param bool default_limits_per_method: whether default limits are applied
     per method, per route or as a combination of all method per route.
    :param function default_limits_exempt_when: a function that should return
     True/False to decide if the default limits should be skipped
    :param function default_limits_deduct_when: a function that receives the
     current :class:`flask.Response` object and returns True/False to decide
     if a deduction should be made from the default rate limit(s)
    :param list application_limits: a variable list of strings or callables
     returning strings for limits that are applied to the entire application
     (i.e a shared limit for all routes)
    :param function key_func: a callable that returns the domain to rate limit
      by.
    :param bool headers_enabled: whether ``X-RateLimit`` response headers are
     written.
    :param str strategy: the strategy to use.
     Refer to :ref:`ratelimit-strategy`
    :param str storage_uri: the storage location.
     Refer to :ref:`ratelimit-conf`
    :param dict storage_options: kwargs to pass to the storage implementation
     upon instantiation.
    :param bool auto_check: whether to automatically check the rate limit in
     the before_request chain of the application. default ``True``
    :param bool swallow_errors: whether to swallow errors when hitting a rate
     limit. An exception will still be logged. default ``False``
    :param list in_memory_fallback: a variable list of strings or callables
     returning strings denoting fallback limits to apply when the storage is
     down.
    :param bool in_memory_fallback_enabled: simply falls back to in memory
     storage when the main storage is down and inherits the original limits.
    :param str retry_after: Allows configuration of how the value of the
     `Retry-After` header is rendered. One of `http-date` or `delta-seconds`.
    :param str key_prefix: prefix prepended to rate limiter keys.
    """

    def __init__(
        self,
        app=None,
        key_func=None,
        global_limits=[],
        default_limits=[],
        default_limits_per_method=False,
        default_limits_exempt_when=None,
        default_limits_deduct_when=None,
        application_limits=[],
        headers_enabled=False,
        strategy=None,
        storage_uri=None,
        storage_options={},
        auto_check=True,
        swallow_errors=False,
        in_memory_fallback=[],
        in_memory_fallback_enabled=False,
        retry_after=None,
        key_prefix="",
        enabled=True
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
            in_memory_fallback_enabled
            or len(in_memory_fallback) > 0
        )
        self._exempt_routes = set()
        self._request_filters = []
        self._headers_enabled = headers_enabled
        self._header_mapping = {}
        self._retry_after = retry_after
        self._strategy = strategy
        self._storage_uri = storage_uri
        self._storage_options = storage_options
        self._auto_check = auto_check
        self._swallow_errors = swallow_errors
        if not key_func:
            warnings.warn(
                "Use of the default `get_ipaddr` function is discouraged."
                " Please refer to"
                " https://flask-limiter.readthedocs.org/#rate-limit-domain"
                " for the recommended configuration", UserWarning
            )
        if global_limits:
            self.__raise_global_limits_warning()

        self._key_func = key_func or get_ipaddr
        self._key_prefix = key_prefix

        for limit in set(global_limits + default_limits):
            self._default_limits.extend(
                [
                    LimitGroup(
                        limit, self._key_func, None, False, None, None,
                        None, None, None
                    )
                ]
            )
        for limit in application_limits:
            self._application_limits.extend(
                [
                    LimitGroup(
                        limit, self._key_func, "global", False, None, None,
                        None, None, None
                    )
                ]
            )
        for limit in in_memory_fallback:
            self._in_memory_fallback.extend(
                [
                    LimitGroup(
                        limit, self._key_func, None, False, None, None,
                        None, None, None
                    )
                ]
            )
        self._route_limits = {}
        self._dynamic_route_limits = {}
        self._blueprint_limits = {}
        self._blueprint_dynamic_limits = {}
        self._blueprint_exempt = set()
        self._storage = self._limiter = None
        self._storage_dead = False
        self._fallback_limiter = None
        self.__check_backend_count = 0
        self.__last_check_backend = time.time()
        self.__marked_for_limiting = {}

        class BlackHoleHandler(logging.StreamHandler):
            def emit(*_):
                return

        self.logger.addHandler(BlackHoleHandler())
        if app:
            self.init_app(app)

    def init_app(self, app):
        """
        :param app: :class:`flask.Flask` instance to rate limit.
        """
        config = app.config
        self.enabled = config.setdefault(C.ENABLED, self.enabled)
        if not self.enabled:
            return

        self._default_limits_per_method = config.setdefault(
            C.DEFAULT_LIMITS_PER_METHOD, self._default_limits_per_method
        )
        self._default_limits_exempt_when = config.setdefault(
            C.DEFAULT_LIMITS_EXEMPT_WHEN, self._default_limits_exempt_when
        )
        self._default_limits_deduct_when = config.setdefault(
            C.DEFAULT_LIMITS_DEDUCT_WHEN, self._default_limits_deduct_when
        )
        self._swallow_errors = config.setdefault(
            C.SWALLOW_ERRORS, self._swallow_errors
        )
        self._headers_enabled = (
            self._headers_enabled
            or config.setdefault(C.HEADERS_ENABLED, False)
        )
        self._storage_options.update(config.get(C.STORAGE_OPTIONS, {}))
        self._storage = storage_from_string(
            self._storage_uri
            or config.setdefault(C.STORAGE_URL, 'memory://'),
            **self._storage_options
        )
        strategy = (
            self._strategy
            or config.setdefault(C.STRATEGY, 'fixed-window')
        )
        if strategy not in STRATEGIES:
            raise ConfigurationError(
                "Invalid rate limiting strategy %s" % strategy
            )
        self._limiter = STRATEGIES[strategy](self._storage)

        # TODO: this should be made consistent with the rest of the
        #  configuration
        self._header_mapping = {
            HEADERS.RESET: self._header_mapping.get(
                HEADERS.RESET, config.get(
                    C.HEADER_RESET, "X-RateLimit-Reset"
                )
            ),
            HEADERS.REMAINING: self._header_mapping.get(
                HEADERS.REMAINING, config.get(
                    C.HEADER_REMAINING, "X-RateLimit-Remaining"
                )
            ),
            HEADERS.LIMIT: self._header_mapping.get(
                HEADERS.LIMIT, config.get(
                    C.HEADER_LIMIT, "X-RateLimit-Limit"
                )
            ),
            HEADERS.RETRY_AFTER: self._header_mapping.get(
                HEADERS.RETRY_AFTER, config.get(
                    C.HEADER_RETRY_AFTER, "Retry-After"
                )
            ),
        }
        self._retry_after = (
            self._retry_after or config.get(C.HEADER_RETRY_AFTER_VALUE)
        )

        self._key_prefix = (self._key_prefix or config.get(C.KEY_PREFIX))

        app_limits = config.get(C.APPLICATION_LIMITS, None)
        if not self._application_limits and app_limits:
            self._application_limits = [
                LimitGroup(
                    app_limits, self._key_func, "global", False, None, None,
                    None, None, None
                )
            ]

        if config.get(C.GLOBAL_LIMITS, None):
            self.__raise_global_limits_warning()

        conf_limits = config.get(
            C.GLOBAL_LIMITS, config.get(C.DEFAULT_LIMITS, None)
        )
        if not self._default_limits and conf_limits:
            self._default_limits = [
                LimitGroup(
                    conf_limits, self._key_func, None, False, None, None,
                    None, None, None
                )
            ]
        for limit in self._default_limits:
            limit.per_method = self._default_limits_per_method
            limit.exempt_when = self._default_limits_exempt_when
            limit.deduct_when = self._default_limits_deduct_when

        self.__configure_fallbacks(app, strategy)

        # purely for backward compatibility as stated in flask documentation
        if not hasattr(app, 'extensions'):
            app.extensions = {}  # pragma: no cover

        if not app.extensions.get('limiter'):
            if self._auto_check:
                app.before_request(self.__check_request_limit)
            app.after_request(self.__inject_headers)

        app.extensions['limiter'] = self
        self.initialized = True

    def __configure_fallbacks(self, app, strategy):
        config = app.config
        fallback_enabled = config.get(C.IN_MEMORY_FALLBACK_ENABLED, False)
        fallback_limits = config.get(C.IN_MEMORY_FALLBACK, None)
        if not self._in_memory_fallback and fallback_limits:
            self._in_memory_fallback = [
                LimitGroup(
                    fallback_limits, self._key_func, None, False, None, None,
                    None, None, None
                )
            ]
        if not self._in_memory_fallback_enabled:
            self._in_memory_fallback_enabled = (
                fallback_enabled
                or len(self._in_memory_fallback) > 0
            )

        if self._in_memory_fallback_enabled:
            self._fallback_storage = MemoryStorage()
            self._fallback_limiter = STRATEGIES[strategy](
                self._fallback_storage
            )

    def __should_check_backend(self):
        if self.__check_backend_count > MAX_BACKEND_CHECKS:
            self.__check_backend_count = 0
        if time.time() - self.__last_check_backend > pow(
            2, self.__check_backend_count
        ):
            self.__last_check_backend = time.time()
            self.__check_backend_count += 1
            return True
        return False

    def check(self):
        """
        check the limits for the current request

        :raises: RateLimitExceeded
        """
        self.__check_request_limit(False)

    def reset(self):
        """
        resets the storage if it supports being reset
        """
        try:
            self._storage.reset()
            self.logger.info("Storage has been reset and all limits cleared")
        except NotImplementedError:
            self.logger.warning(
                "This storage type does not support being reset"
            )

    @property
    def limiter(self):
        if self._storage_dead and self._in_memory_fallback_enabled:
            return self._fallback_limiter
        else:
            return self._limiter

    def __check_conditional_deductions(self, response):
        for lim, args in getattr(g, 'conditional_deductions', {}).items():
            if lim.deduct_when(response):
                self.limiter.hit(lim.limit, *args)

        return response

    def __inject_headers(self, response):
        self.__check_conditional_deductions(response)
        current_limit = getattr(g, 'view_rate_limit', None)
        if self.enabled and self._headers_enabled and current_limit:
            try:
                window_stats = self.limiter.get_window_stats(*current_limit)
                reset_in = 1 + window_stats[0]
                response.headers.add(
                    self._header_mapping[HEADERS.LIMIT],
                    str(current_limit[0].amount)
                )
                response.headers.add(
                    self._header_mapping[HEADERS.REMAINING], window_stats[1]
                )
                response.headers.add(
                    self._header_mapping[HEADERS.RESET], reset_in
                )

                # response may have an existing retry after
                existing_retry_after_header = response.headers.get(
                    'Retry-After'
                )

                if existing_retry_after_header is not None:
                    # might be in http-date format
                    retry_after = parse_date(existing_retry_after_header)

                    # parse_date failure returns None
                    if retry_after is None:
                        retry_after = time.time() + int(
                            existing_retry_after_header
                        )

                    if isinstance(retry_after, datetime.datetime):
                        retry_after = time.mktime(retry_after.timetuple())

                    reset_in = max(retry_after, reset_in)

                # set the header instead of using add
                response.headers.set(
                    self._header_mapping[HEADERS.RETRY_AFTER],
                    self._retry_after == 'http-date' and http_date(reset_in)
                    or int(reset_in - time.time())
                )
            except:  # noqa: E722
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
                            "Failed to update rate limit headers. "
                            "Swallowing error"
                        )
                    else:
                        six.reraise(*sys.exc_info())
        return response

    def __evaluate_limits(self, endpoint, limits):
        failed_limit = None
        limit_for_header = None
        if not getattr(g, "conditional_deductions", None):
            g.conditional_deductions = {}

        for lim in limits:
            limit_scope = lim.scope or endpoint

            if lim.is_exempt or lim.method_exempt:
                continue

            if lim.per_method:
                limit_scope += ":%s" % request.method
            limit_key = lim.key_func()
            args = [limit_key, limit_scope]
            if not all(args):
                self.logger.error(
                    "Skipping limit: %s. Empty value found in parameters.",
                    lim.limit
                )
                continue

            if self._key_prefix:
                args = [self._key_prefix] + args

            if lim.deduct_when:
                g.conditional_deductions[lim] = args
                method = self.limiter.test
            else:
                method = self.limiter.hit

            if not limit_for_header or lim.limit < limit_for_header[0]:
                limit_for_header = [lim.limit] + args

            if not method(lim.limit, *args):
                self.logger.warning(
                    "ratelimit %s (%s) exceeded at endpoint: %s",
                    lim.limit, limit_key, limit_scope
                )
                failed_limit = lim
                limit_for_header = [lim.limit] + args
                break

        g.view_rate_limit = limit_for_header

        if failed_limit:
            raise RateLimitExceeded(failed_limit)

    def __check_request_limit(self, in_middleware=True):
        endpoint = request.endpoint or ""
        view_func = current_app.view_functions.get(endpoint, None)
        name = (
            "%s.%s" % (view_func.__module__, view_func.__name__)
            if view_func else ""
        )
        if (
            not request.endpoint
            or not (self.enabled and self.initialized)
            or view_func == current_app.send_static_file
            or name in self._exempt_routes
            or request.blueprint in self._blueprint_exempt
            or any(fn() for fn in self._request_filters)
            or g.get("_rate_limiting_complete")
        ):
            return
        limits, dynamic_limits = [], []

        # this is to ensure backward compatibility with behavior that
        # existed accidentally, i.e::
        #
        # @limiter.limit(...)
        # @app.route('...')
        # def func(...):
        #
        # The above setup would work in pre 1.0 versions because the decorator
        # was not acting immediately and instead simply registering the rate
        # limiting. The correct way to use the decorator is to wrap
        # the limiter with the route, i.e::
        #
        # @app.route(...)
        # @limiter.limit(...)
        # def func(...):

        implicit_decorator = view_func in self.__marked_for_limiting.get(
            name, []
        )

        if not in_middleware or implicit_decorator:
            limits = (
                name in self._route_limits and self._route_limits[name] or []
            )
            dynamic_limits = []
            if name in self._dynamic_route_limits:
                for lim in self._dynamic_route_limits[name]:
                    try:
                        dynamic_limits.extend(list(lim))
                    except ValueError as e:
                        self.logger.error(
                            "failed to load ratelimit for "
                            "view function %s (%s)",
                            name, e
                        )
        if request.blueprint:
            if (
                request.blueprint in self._blueprint_dynamic_limits
                and not dynamic_limits
            ):
                for limit_group in self._blueprint_dynamic_limits[
                    request.blueprint
                ]:
                    try:
                        dynamic_limits.extend(
                            [
                                Limit(
                                    limit.limit, limit.key_func, limit.scope,
                                    limit.per_method, limit.methods,
                                    limit.error_message, limit.exempt_when,
                                    limit.override_defaults, limit.deduct_when,
                                ) for limit in limit_group
                            ]
                        )
                    except ValueError as e:
                        self.logger.error(
                            "failed to load ratelimit for blueprint %s (%s)",
                            request.blueprint, e
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
                        all_limits = list(
                            itertools.chain(*self._in_memory_fallback)
                        )
            if not all_limits:
                route_limits = limits + dynamic_limits
                all_limits = list(
                    itertools.chain(*self._application_limits)
                ) if in_middleware else []
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
                    (explicit_limits_exempt or combined_defaults)
                    and not before_request_context
                    or implicit_decorator
                ):
                    all_limits += list(itertools.chain(*self._default_limits))
            self.__evaluate_limits(endpoint, all_limits)
        except Exception as e:
            if isinstance(e, RateLimitExceeded):
                six.reraise(*sys.exc_info())
            if self._in_memory_fallback_enabled and not self._storage_dead:
                self.logger.warning(
                    "Rate limit storage unreachable - falling back to"
                    " in-memory storage"
                )
                self._storage_dead = True
                self.__check_request_limit(in_middleware)
            else:
                if self._swallow_errors:
                    self.logger.exception(
                        "Failed to rate limit. Swallowing error"
                    )
                else:
                    six.reraise(*sys.exc_info())

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
        deduct_when=None
    ):
        _scope = scope if shared else None

        def _inner(obj):
            func = key_func or self._key_func
            is_route = not isinstance(obj, Blueprint)
            name = "%s.%s" % (
                obj.__module__, obj.__name__
            ) if is_route else obj.name
            dynamic_limit, static_limits = None, []
            if callable(limit_value):
                dynamic_limit = LimitGroup(
                    limit_value, func, _scope, per_method, methods,
                    error_message, exempt_when, override_defaults,
                    deduct_when
                )
            else:
                try:
                    static_limits = list(
                        LimitGroup(
                            limit_value, func, _scope, per_method, methods,
                            error_message, exempt_when, override_defaults,
                            deduct_when
                        )
                    )
                except ValueError as e:
                    self.logger.error(
                        "failed to configure %s %s (%s)", "view function"
                        if is_route else "blueprint", name, e
                    )
            if isinstance(obj, Blueprint):
                if dynamic_limit:
                    self._blueprint_dynamic_limits.setdefault(
                        name, []
                    ).append(dynamic_limit)
                else:
                    self._blueprint_limits.setdefault(
                        name, []
                    ).extend(static_limits)
            else:
                self.__marked_for_limiting.setdefault(name, []).append(obj)
                if dynamic_limit:
                    self._dynamic_route_limits.setdefault(
                        name, []
                    ).append(dynamic_limit)
                else:
                    self._route_limits.setdefault(
                        name, []
                    ).extend(static_limits)

                @wraps(obj)
                def __inner(*a, **k):
                    if (
                        self._auto_check
                        and not g.get("_rate_limiting_complete")
                    ):
                        self.__check_request_limit(False)
                        g._rate_limiting_complete = True
                    return obj(*a, **k)
                return __inner
        return _inner

    def limit(
        self,
        limit_value,
        key_func=None,
        per_method=False,
        methods=None,
        error_message=None,
        exempt_when=None,
        override_defaults=True,
        deduct_when=None,
    ):
        """
        decorator to be used for rate limiting individual routes or blueprints.

        :param limit_value: rate limit string or a callable that returns a
         string. :ref:`ratelimit-string` for more details.
        :param function key_func: function/lambda to extract the unique
         identifier for the rate limit. defaults to remote address of the
         request.
        :param bool per_method: whether the limit is sub categorized into the
         http method of the request.
        :param list methods: if specified, only the methods in this list will
         be rate limited (default: None).
        :param error_message: string (or callable that returns one) to override
         the error message used in the response.
        :param function exempt_when: function/lambda used to decide if the rate
         limit should skipped.
        :param bool override_defaults:  whether the decorated limit overrides
         the default limits. (default: True)
        :param function deduct_when: a function that receives the current
         :class:`flask.Response` object and returns True/False to decide if a
         deduction should be done from the rate limit
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
        )

    def shared_limit(
        self,
        limit_value,
        scope,
        key_func=None,
        error_message=None,
        exempt_when=None,
        override_defaults=True,
        deduct_when=None,
    ):
        """
        decorator to be applied to multiple routes sharing the same rate limit.

        :param limit_value: rate limit string or a callable that returns a
         string. :ref:`ratelimit-string` for more details.
        :param scope: a string or callable that returns a string
         for defining the rate limiting scope.
        :param function key_func: function/lambda to extract the unique
         identifier for the rate limit. defaults to remote address of the
         request.
        :param error_message: string (or callable that returns one) to override
         the error message used in the response.
        :param function exempt_when: function/lambda used to decide if the rate
         limit should skipped.
        :param bool override_defaults:  whether the decorated limit overrides
         the default limits. (default: True)
        :param function deduct_when: a function that receives the current
         :class:`flask.Response`  object and returns True/False to decide if a
         deduction should be done from the rate limit
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
        )

    def exempt(self, obj):
        """
        decorator to mark a view or all views in a blueprint as exempt from
        rate limits.
        """
        if not isinstance(obj, Blueprint):
            name = "%s.%s" % (obj.__module__, obj.__name__)

            @wraps(obj)
            def __inner(*a, **k):
                return obj(*a, **k)

            self._exempt_routes.add(name)
            return __inner
        else:
            self._blueprint_exempt.add(obj.name)

    def request_filter(self, fn):
        """
        decorator to mark a function as a filter to be executed
        to check if the request is exempt from rate limiting.
        """
        self._request_filters.append(fn)
        return fn

    def __raise_global_limits_warning(self):
        warnings.warn(
            "global_limits was a badly named configuration since it is "
            "actually a default limit and not a globally shared limit. Use "
            "default_limits if you want to provide a default or use "
            "application_limits if you intend to really have a global "
            "shared limit", UserWarning
        )
