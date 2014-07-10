"""
the flask extension
"""

from functools import wraps
import logging

from flask import request, current_app, g

from .errors import RateLimitExceeded, ConfigurationError
from flask.ext.limiter.storage import storage_from_string
from .strategies import STRATEGIES
from .util import parse_many, get_ipaddr

class C:
    ENABLED = "RATELIMIT_ENABLED"
    HEADERS_ENABLED = "RATELIMIT_HEADERS_ENABLED"
    STORAGE_URL = "RATELIMIT_STORAGE_URL"
    STRATEGY = "RATELIMIT_STRATEGY"
    GLOBAL_LIMITS = "RATELIMIT_GLOBAL"


class ExtLimit(object):
    """
    simple wrapper to encapsulate limits and their context
    """
    def __init__(self, limit, key_func, scope, per_method):
        self._limit = limit
        self.key_func = key_func
        self._scope = scope
        self.per_method = per_method

    @property
    def limit(self):
        return self._limit() if callable(self._limit) else self._limit

    @property
    def scope(self):
        return self._scope(request.endpoint) if callable(self._scope) else self._scope

class Limiter(object):
    """
    :param app: :class:`flask.Flask` instance to initialize the extension
     with.
    :param list global_limits: a variable list of strings denoting global
     limits to apply to all routes. :ref:`ratelimit-string` for  more details.
    :param function key_func: a callable that returns the domain to rate limit by.
     Defaults to the remote address of the request.
    :param bool headers_enabled: whether ``X-RateLimit`` response headers are written.
    :param str strategy: the strategy to use. refer to :ref:`ratelimit-strategy`
    :param str storage_uri: the storage location. refer to :ref:`ratelimit-conf`
    """

    def __init__(self, app=None
                 , key_func=get_ipaddr
                 , global_limits=[]
                 , headers_enabled=False
                 , strategy=None
                 , storage_uri=None
    ):
        self.app = app
        self.enabled = True
        self.global_limits = []
        self.exempt_routes = []
        self.request_filters = []
        self.headers_enabled = headers_enabled
        self.strategy = strategy
        self.storage_uri = storage_uri
        for limit in global_limits:
            self.global_limits.extend(
                [
                    ExtLimit(
                        limit, key_func, None, False
                    ) for limit in parse_many(limit)
                ]
            )
        self.route_limits = {}
        self.dynamic_route_limits = {}
        self.storage = self.limiter = None
        self.key_func = key_func
        self.logger = logging.getLogger("flask-limiter")
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
        self.headers_enabled = (
            self.headers_enabled
            or app.config.setdefault(C.HEADERS_ENABLED, True)
        )
        self.storage = storage_from_string(
            self.storage_uri
            or app.config.setdefault(C.STORAGE_URL, 'memory://')
        )
        strategy = (
            self.strategy
            or app.config.setdefault(C.STRATEGY, 'fixed-window')
        )
        if strategy not in STRATEGIES:
            raise ConfigurationError("Invalid rate limiting strategy %s" % strategy)
        self.limiter = STRATEGIES[strategy](self.storage)
        conf_limits = app.config.get(C.GLOBAL_LIMITS, None)
        if not self.global_limits and conf_limits:
            self.global_limits = [
                ExtLimit(
                    limit, self.key_func, None, False
                ) for limit in parse_many(conf_limits)
            ]
        app.before_request(self.__check_request_limit)
        app.after_request(self.__inject_headers)

        # purely for backward compatibility as stated in flask documentation
        if not hasattr(app, 'extensions'):
            app.extensions = {} # pragma: no cover
        app.extensions['limiter'] = self

    def __inject_headers(self, response):
        current_limit = getattr(g, 'view_rate_limit', None)
        if self.enabled and self.headers_enabled and current_limit:
            window_stats = self.limiter.get_window_stats(*current_limit)
            response.headers.add(
                'X-RateLimit-Limit',
                str(current_limit[0].amount)
            )
            response.headers.add(
                'X-RateLimit-Remaining',
                window_stats[1]
            )
            response.headers.add(
                'X-RateLimit-Reset',
                window_stats[0]
            )
        return response

    def __check_request_limit(self):
        endpoint = request.endpoint or ""
        view_func = current_app.view_functions.get(endpoint, None)
        name = ("%s.%s" % (
                view_func.__module__, view_func.__name__
            ) if view_func else ""
        )
        if (view_func == current_app.send_static_file
            or name in self.exempt_routes
            or not self.enabled
            or any(fn() for fn in self.request_filters)
        ):
            return
        limits = (
            name in self.route_limits and self.route_limits[name]
            or []
        )
        dynamic_limits = []
        if name in self.dynamic_route_limits:
            for lim in self.dynamic_route_limits[name]:
                try:
                    dynamic_limits.extend(
                        ExtLimit(
                            limit, lim.key_func, lim.scope, lim.per_method
                        ) for limit in parse_many(lim.limit)
                    )
                except ValueError as e:
                    self.logger.error(
                        "failed to load ratelimit for view function %s (%s)"
                        , name, e
                    )

        failed_limit = None
        limit_for_header = None
        for lim in (limits + dynamic_limits or self.global_limits):
            limit_scope = lim.scope or endpoint
            if lim.per_method:
                limit_scope += ":%s" % request.method
            if not limit_for_header or lim.limit < limit_for_header[0]:
                limit_for_header = (lim.limit, lim.key_func(), limit_scope)
            if not self.limiter.hit(lim.limit, lim.key_func(), limit_scope):
                self.logger.warn(
                    "ratelimit %s (%s) exceeded at endpoint: %s"
                    , lim.limit, lim.key_func(), limit_scope
                )
                failed_limit = lim.limit
                limit_for_header = (lim.limit, lim.key_func(), limit_scope)
        g.view_rate_limit = limit_for_header

        if failed_limit:
            raise RateLimitExceeded(failed_limit)

    def __limit_decorator(self, limit_value,
                          key_func=None, shared=False,
                          scope=None,
                          per_method=False):
        _scope = scope if shared else None

        def _inner(fn):
            name = "%s.%s" % (fn.__module__, fn.__name__)

            @wraps(fn)
            def __inner(*a, **k):
                return fn(*a, **k)
            func = key_func or self.key_func
            if callable(limit_value):
                self.dynamic_route_limits.setdefault(name, []).append(
                    ExtLimit(limit_value, func, _scope, per_method)
                )
            else:
                try:
                    self.route_limits.setdefault(name, []).extend(
                        [ExtLimit(
                            limit, func, _scope, per_method
                        ) for limit in parse_many(limit_value)]
                    )
                except ValueError as e:
                    self.logger.error(
                        "failed to configure view function %s (%s)", name, e
                    )
            return __inner
        return _inner


    def limit(self, limit_value, key_func=None, per_method=False):
        """
        decorator to be used for rate limiting individual routes.

        :param limit_value: rate limit string or a callable that returns a string.
         :ref:`ratelimit-string` for more details.
        :param function key_func: function/lambda to extract the unique identifier for
         the rate limit. defaults to remote address of the request.
        :param bool per_method: whether the limit is sub categorized into the http
         method of the request.
        :return:
        """
        return self.__limit_decorator(limit_value, key_func, per_method=per_method)


    def shared_limit(self, limit_value, scope, key_func=None):
        """
        decorator to be applied to multiple routes sharing the same rate limit.

        :param limit_value: rate limit string or a callable that returns a string.
         :ref:`ratelimit-string` for more details.
        :param scope: a string or callable that returns a string
         for defining the rate limiting scope.
        :param function key_func: function/lambda to extract the unique identifier for
         the rate limit. defaults to remote address of the request.
        """
        return self.__limit_decorator(limit_value, key_func, True, scope)



    def exempt(self, fn):
        """
        decorator to mark a view as exempt from rate limits.
        """
        name = "%s.%s" % (fn.__module__, fn.__name__)
        @wraps(fn)
        def __inner(*a, **k):
            return fn(*a, **k)
        self.exempt_routes.append(name)
        return __inner

    def request_filter(self, fn):
        """
        decorator to mark a function as a filter to be executed
        to check if the request is exempt from rate limiting.
        """
        self.request_filters.append(fn)
        return fn

