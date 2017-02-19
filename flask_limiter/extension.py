"""
the flask extension
"""
import warnings
from functools import wraps
import logging

from flask import request, current_app, g, Blueprint
from werkzeug.http import http_date

from limits.errors import ConfigurationError
from limits.storage import storage_from_string, MemoryStorage
from limits.strategies import STRATEGIES
from limits.util import parse_many
import six
import sys
import time
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
    APPLICATION_LIMITS = "RATELIMIT_APPLICATION"
    HEADER_LIMIT = "RATELIMIT_HEADER_LIMIT"
    HEADER_REMAINING = "RATELIMIT_HEADER_REMAINING"
    HEADER_RESET = "RATELIMIT_HEADER_RESET"
    SWALLOW_ERRORS = "RATELIMIT_SWALLOW_ERRORS"
    IN_MEMORY_FALLBACK = "RATELIMIT_IN_MEMORY_FALLBACK"
    HEADER_RETRY_AFTER = "RATELIMIT_HEADER_RETRY_AFTER"
    HEADER_RETRY_AFTER_VALUE = "RATELIMIT_HEADER_RETRY_AFTER_VALUE"

class HEADERS:
    RESET = 1
    REMAINING = 2
    LIMIT = 3
    RETRY_AFTER = 4

MAX_BACKEND_CHECKS = 5

class ExtLimit(object):
    """
    simple wrapper to encapsulate limits and their context
    """
    def __init__(self, limit, key_func, scope, per_method, methods, error_message,
                 exempt_when):
        self._limit = limit
        self.key_func = key_func
        self._scope = scope
        self.per_method = per_method
        self.methods = methods and [m.lower() for m in methods] or methods
        self.error_message = error_message
        self.exempt_when = exempt_when

    @property
    def limit(self):
        return self._limit() if callable(self._limit) else self._limit

    @property
    def scope(self):
        return self._scope(request.endpoint) if callable(self._scope) else self._scope

    @property
    def is_exempt(self):
        """Check if the limit is exempt."""
        return self.exempt_when and self.exempt_when()

class Limiter(object):
    """
    :param app: :class:`flask.Flask` instance to initialize the extension
     with.
    :param list default_limits: a variable list of strings denoting global
     limits to apply to all routes. :ref:`ratelimit-string` for  more details.
    :param list application_limits: a variable list of strings for limits that
     are applied to the entire application (i.e a shared limit for all routes)
    :param function key_func: a callable that returns the domain to rate limit by.
    :param bool headers_enabled: whether ``X-RateLimit`` response headers are written.
    :param str strategy: the strategy to use. refer to :ref:`ratelimit-strategy`
    :param str storage_uri: the storage location. refer to :ref:`ratelimit-conf`
    :param dict storage_options: kwargs to pass to the storage implementation upon
      instantiation.
    :param bool auto_check: whether to automatically check the rate limit in the before_request
     chain of the application. default ``True``
    :param bool swallow_errors: whether to swallow errors when hitting a rate limit.
     An exception will still be logged. default ``False``
    :param list in_memory_fallback: a variable list of strings denoting fallback
     limits to apply when the storage is down.
    """

    def __init__(self, app=None
                 , key_func=None
                 , global_limits=[]
                 , default_limits=[]
                 , application_limits=[]
                 , headers_enabled=False
                 , strategy=None
                 , storage_uri=None
                 , storage_options={}
                 , auto_check=True
                 , swallow_errors=False
                 , in_memory_fallback=[]
                 , retry_after=None
    ):
        self.app = app
        self.logger = logging.getLogger("flask-limiter")

        self.enabled = True
        self._default_limits = []
        self._application_limits = []
        self._in_memory_fallback = []
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
                " Please refer to https://flask-limiter.readthedocs.org/#rate-limit-domain"
                " for the recommended configuration",
                UserWarning
            )
        if global_limits:
            self.raise_global_limits_warning()

        self._key_func = key_func or get_ipaddr
        for limit in set(global_limits + default_limits):
            self._default_limits.extend(
                [
                    ExtLimit(
                        limit, self._key_func, None, False, None, None, None
                    ) for limit in parse_many(limit)
                ]
            )
        for limit in application_limits:
            self._application_limits.extend(
                [
                    ExtLimit(
                        limit, self._key_func, "global", False, None, None, None
                    ) for limit in parse_many(limit)
                ]
            )
        for limit in in_memory_fallback:
            self._in_memory_fallback.extend(
                [
                    ExtLimit(
                        limit, self._key_func, None, False, None, None, None
                    ) for limit in parse_many(limit)
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
        self.enabled = app.config.setdefault(C.ENABLED, True)
        self._swallow_errors = app.config.setdefault(
            C.SWALLOW_ERRORS, self._swallow_errors
        )
        self._headers_enabled = (
            self._headers_enabled
            or app.config.setdefault(C.HEADERS_ENABLED, False)
        )
        self._storage_options.update(
            app.config.get(C.STORAGE_OPTIONS, {})
        )
        self._storage = storage_from_string(
            self._storage_uri
            or app.config.setdefault(C.STORAGE_URL, 'memory://'),
            ** self._storage_options
        )
        strategy = (
            self._strategy
            or app.config.setdefault(C.STRATEGY, 'fixed-window')
        )
        if strategy not in STRATEGIES:
            raise ConfigurationError("Invalid rate limiting strategy %s" % strategy)
        self._limiter = STRATEGIES[strategy](self._storage)
        self._header_mapping.update({
           HEADERS.RESET : self._header_mapping.get(HEADERS.RESET,None) or app.config.setdefault(C.HEADER_RESET, "X-RateLimit-Reset"),
           HEADERS.REMAINING : self._header_mapping.get(HEADERS.REMAINING,None) or app.config.setdefault(C.HEADER_REMAINING, "X-RateLimit-Remaining"),
           HEADERS.LIMIT : self._header_mapping.get(HEADERS.LIMIT,None) or app.config.setdefault(C.HEADER_LIMIT, "X-RateLimit-Limit"),
           HEADERS.RETRY_AFTER : self._header_mapping.get(HEADERS.RETRY_AFTER,None) or app.config.setdefault(C.HEADER_RETRY_AFTER, "Retry-After"),
        })
        self._retry_after = (
            self._retry_after
            or app.config.get(C.HEADER_RETRY_AFTER_VALUE)
        )

        app_limits = app.config.get(C.APPLICATION_LIMITS, None)
        if not self._application_limits and app_limits:
            self._application_limits = [
                ExtLimit(
                    limit, self._key_func, "global", False, None, None, None
                ) for limit in parse_many(app_limits)
            ]

        if app.config.get(C.GLOBAL_LIMITS, None):
            self.raise_global_limits_warning()
        conf_limits = app.config.get(C.GLOBAL_LIMITS, app.config.get(C.DEFAULT_LIMITS, None))
        if not self._default_limits and conf_limits:
            self._default_limits = [
                ExtLimit(
                    limit, self._key_func, None, False, None, None, None
                ) for limit in parse_many(conf_limits)
            ]
        fallback_limits = app.config.get(C.IN_MEMORY_FALLBACK, None)
        if not self._in_memory_fallback and fallback_limits:
            self._in_memory_fallback = [
                ExtLimit(
                    limit, self._key_func, None, False, None, None, None
                ) for limit in parse_many(fallback_limits)
                ]
        if self._auto_check:
            app.before_request(self.__check_request_limit)
        app.after_request(self.__inject_headers)

        if self._in_memory_fallback:
            self._fallback_storage = MemoryStorage()
            self._fallback_limiter = STRATEGIES[strategy](self._fallback_storage)

        # purely for backward compatibility as stated in flask documentation
        if not hasattr(app, 'extensions'):
            app.extensions = {} # pragma: no cover
        app.extensions['limiter'] = self

    def __should_check_backend(self):
        if self.__check_backend_count > MAX_BACKEND_CHECKS:
            self.__check_backend_count = 0
        if time.time() - self.__last_check_backend > pow(2, self.__check_backend_count):
            self.__last_check_backend = time.time()
            self.__check_backend_count += 1
            return True
        return False

    def check(self):
        """
        check the limits for the current request

        :raises: RateLimitExceeded
        """
        self.__check_request_limit()

    def reset(self):
        """
        resets the storage if it supports being reset
        """
        try:
            self._storage.reset()
            self.logger.info("Storage has been reset and all limits cleared")
        except NotImplementedError:
            self.logger.warning("This storage type does not support being reset")

    @property
    def limiter(self):
        if self._storage_dead and self._in_memory_fallback:
            return self._fallback_limiter
        else:
            return self._limiter

    def __inject_headers(self, response):
        current_limit = getattr(g, 'view_rate_limit', None)
        if self.enabled and self._headers_enabled and current_limit:
            window_stats = self.limiter.get_window_stats(*current_limit)
            response.headers.add(
                self._header_mapping[HEADERS.LIMIT],
                str(current_limit[0].amount)
            )
            response.headers.add(
                self._header_mapping[HEADERS.REMAINING],
                window_stats[1]
            )
            response.headers.add(
                self._header_mapping[HEADERS.RESET],
                window_stats[0]
            )
            response.headers.add(
                self._header_mapping[HEADERS.RETRY_AFTER],
                self._retry_after == 'http-date' and http_date(window_stats[0])
                    or int(window_stats[0] - time.time())
            )
        return response

    def __check_request_limit(self):
        endpoint = request.endpoint or ""
        view_func = current_app.view_functions.get(endpoint, None)
        name = ("%s.%s" % (
                view_func.__module__, view_func.__name__
            ) if view_func else ""
        )
        if (not request.endpoint
            or not self.enabled
            or view_func == current_app.send_static_file
            or name in self._exempt_routes
            or request.blueprint in self._blueprint_exempt
            or any(fn() for fn in self._request_filters)
        ):
            return
        limits = (
            name in self._route_limits and self._route_limits[name]
            or []
        )
        dynamic_limits = []
        if name in self._dynamic_route_limits:
            for lim in self._dynamic_route_limits[name]:
                try:
                    dynamic_limits.extend(
                        ExtLimit(
                            limit, lim.key_func, lim.scope, lim.per_method,
                            lim.methods, lim.error_message, lim.exempt_when
                        ) for limit in parse_many(lim.limit)
                    )
                except ValueError as e:
                    self.logger.error(
                        "failed to load ratelimit for view function %s (%s)"
                        , name, e
                    )
        if request.blueprint:
            if (request.blueprint in self._blueprint_dynamic_limits
                and not dynamic_limits
            ):
                for lim in self._blueprint_dynamic_limits[request.blueprint]:
                    try:
                        dynamic_limits.extend(
                            ExtLimit(
                                limit, lim.key_func, lim.scope, lim.per_method,
                                lim.methods, lim.error_message, lim.exempt_when
                            ) for limit in parse_many(lim.limit)
                        )
                    except ValueError as e:
                        self.logger.error(
                            "failed to load ratelimit for blueprint %s (%s)"
                            , request.blueprint, e
                        )
            if (request.blueprint in self._blueprint_limits
                and not limits
            ):
               limits.extend(self._blueprint_limits[request.blueprint])

        failed_limit = None
        limit_for_header = None
        try:
            all_limits = []
            if self._storage_dead and self._fallback_limiter:
                if self.__should_check_backend() and self._storage.check():
                    self.logger.info(
                        "Rate limit storage recovered"
                    )
                    self._storage_dead = False
                    self.__check_backend_count = 0
                else:
                    all_limits = self._in_memory_fallback
            if not all_limits:
                all_limits = self._application_limits + (limits + dynamic_limits or self._default_limits)
            for lim in all_limits:
                limit_scope = lim.scope or endpoint
                if lim.is_exempt:
                    return
                if lim.methods is not None and request.method.lower() not in lim.methods:
                    return
                if lim.per_method:
                    limit_scope += ":%s" % request.method
                if not limit_for_header or lim.limit < limit_for_header[0]:
                    limit_for_header = (lim.limit, lim.key_func(), limit_scope)
                if not self.limiter.hit(lim.limit, lim.key_func(), limit_scope):
                    self.logger.warning(
                        "ratelimit %s (%s) exceeded at endpoint: %s"
                        , lim.limit, lim.key_func(), limit_scope
                    )
                    failed_limit = lim
                    limit_for_header = (lim.limit, lim.key_func(), limit_scope)
                    break

            g.view_rate_limit = limit_for_header

            if failed_limit:
                if failed_limit.error_message:
                    exc_description = failed_limit.error_message if not callable(
                        failed_limit.error_message
                    ) else failed_limit.error_message()
                else:
                    exc_description = six.text_type(failed_limit.limit)
                raise RateLimitExceeded(exc_description)
        except Exception as e: # no qa
            if isinstance(e, RateLimitExceeded):
                six.reraise(*sys.exc_info())
            if self._in_memory_fallback and not self._storage_dead:
                self.logger.warn(
                    "Rate limit storage unreachable - falling back to"
                    " in-memory storage"
                )
                self._storage_dead = True
                self.__check_request_limit()
            else:
                if self._swallow_errors:
                    self.logger.exception(
                        "Failed to rate limit. Swallowing error"
                    )
                else:
                    six.reraise(*sys.exc_info())

    def __limit_decorator(self, limit_value,
                          key_func=None, shared=False,
                          scope=None,
                          per_method=False,
                          methods=None,
                          error_message=None,
                          exempt_when=None):
        _scope = scope if shared else None

        def _inner(obj):
            func = key_func or self._key_func
            is_route = not isinstance(obj, Blueprint)
            name = "%s.%s" % (obj.__module__, obj.__name__) if is_route else obj.name
            dynamic_limit, static_limits = None, []
            if callable(limit_value):
                dynamic_limit = ExtLimit(limit_value, func, _scope, per_method,
                                         methods, error_message, exempt_when)
            else:
                try:
                    static_limits = [ExtLimit(
                        limit, func, _scope, per_method,
                        methods, error_message, exempt_when
                    ) for limit in parse_many(limit_value)]
                except ValueError as e:
                    self.logger.error(
                        "failed to configure %s %s (%s)",
                        "view function" if is_route else "blueprint", name, e
                    )
            if isinstance(obj, Blueprint):
                if dynamic_limit:
                    self._blueprint_dynamic_limits.setdefault(name, []).append(
                        dynamic_limit
                    )
                else:
                    self._blueprint_limits.setdefault(name, []).extend(
                        static_limits
                    )
            else:
                @wraps(obj)
                def __inner(*a, **k):
                    return obj(*a, **k)
                if dynamic_limit:
                    self._dynamic_route_limits.setdefault(name, []).append(
                        dynamic_limit
                    )
                else:
                    self._route_limits.setdefault(name, []).extend(
                        static_limits
                    )
                return __inner
        return _inner


    def limit(self, limit_value, key_func=None, per_method=False,
              methods=None, error_message=None, exempt_when=None):
        """
        decorator to be used for rate limiting individual routes or blueprints.

        :param limit_value: rate limit string or a callable that returns a string.
         :ref:`ratelimit-string` for more details.
        :param function key_func: function/lambda to extract the unique identifier for
         the rate limit. defaults to remote address of the request.
        :param bool per_method: whether the limit is sub categorized into the http
         method of the request.
        :param list methods: if specified, only the methods in this list will be rate
         limited (default: None).
        :param error_message: string (or callable that returns one) to override the
         error message used in the response.
        :return:
        """
        return self.__limit_decorator(limit_value, key_func, per_method=per_method,
                                      methods=methods, error_message=error_message,
                                      exempt_when=exempt_when)


    def shared_limit(self, limit_value, scope, key_func=None,
                     error_message=None, exempt_when=None):
        """
        decorator to be applied to multiple routes sharing the same rate limit.

        :param limit_value: rate limit string or a callable that returns a string.
         :ref:`ratelimit-string` for more details.
        :param scope: a string or callable that returns a string
         for defining the rate limiting scope.
        :param function key_func: function/lambda to extract the unique identifier for
         the rate limit. defaults to remote address of the request.
        :param error_message: string (or callable that returns one) to override the
         error message used in the response.
        """
        return self.__limit_decorator(
            limit_value, key_func, True, scope, error_message=error_message,
            exempt_when=exempt_when
        )


    def exempt(self, obj):
        """
        decorator to mark a view or all views in a blueprint as exempt from rate limits.
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


    def raise_global_limits_warning(self):
        warnings.warn(
            "global_limits was a badly name configuration since it is actually a default limit and not a "
            " globally shared limit. Use default_limits if you want to provide a default or use application_limits "
            " if you intend to really have a global shared limit",
            UserWarning
        )
