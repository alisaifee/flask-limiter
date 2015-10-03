"""
the flask extension
"""

from functools import wraps
import logging

from flask import request, current_app, g, Blueprint

from limits.errors import ConfigurationError
from limits.storage import storage_from_string
from limits.strategies import STRATEGIES
from limits.util import parse_many
import six
import sys
from .errors import RateLimitExceeded
from .util import get_ipaddr

class C:
    ENABLED = "RATELIMIT_ENABLED"
    HEADERS_ENABLED = "RATELIMIT_HEADERS_ENABLED"
    STORAGE_URL = "RATELIMIT_STORAGE_URL"
    STORAGE_OPTIONS = "RATELIMIT_STORAGE_OPTIONS"
    STRATEGY = "RATELIMIT_STRATEGY"
    GLOBAL_LIMITS = "RATELIMIT_GLOBAL"
    HEADER_LIMIT = "RATELIMIT_HEADER_LIMIT"
    HEADER_REMAINING = "RATELIMIT_HEADER_REMAINING"
    HEADER_RESET = "RATELIMIT_HEADER_RESET"
    SWALLOW_ERRORS = "RATELIMIT_SWALLOW_ERRORS"

class HEADERS:
    RESET = 1
    REMAINING = 2
    LIMIT = 3

class ExtLimit(object):
    """
    simple wrapper to encapsulate limits and their context
    """
    def __init__(self, limit, key_func, scope, per_method, methods, error_message):
        self._limit = limit
        self.key_func = key_func
        self._scope = scope
        self.per_method = per_method
        self.methods = methods and [m.lower() for m in methods] or methods
        self.error_message = error_message

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
    :param dict storage_options: kwargs to pass to the storage implementation upon
      instantiation.
    :param bool auto_check: whether to automatically check the rate limit in the before_request
     chain of the application. default ``True``
    :param bool swallow_errors: whether to swallow errors when hitting a rate limit.
     An exception will still be logged. default ``False``
    """

    def __init__(self, app=None
                 , key_func=get_ipaddr
                 , global_limits=[]
                 , headers_enabled=False
                 , strategy=None
                 , storage_uri=None
                 , storage_options={}
                 , auto_check=True
                 , swallow_errors=False
    ):
        self.app = app
        self.enabled = True
        self.global_limits = []
        self.exempt_routes = set()
        self.request_filters = []
        self.headers_enabled = headers_enabled
        self.header_mapping = {}
        self.strategy = strategy
        self.storage_uri = storage_uri
        self.storage_options = storage_options
        self.auto_check = auto_check
        self.swallow_errors = swallow_errors
        for limit in global_limits:
            self.global_limits.extend(
                [
                    ExtLimit(
                        limit, key_func, None, False, None, None
                    ) for limit in parse_many(limit)
                ]
            )
        self.route_limits = {}
        self.dynamic_route_limits = {}
        self.blueprint_limits = {}
        self.blueprint_dynamic_limits = {}
        self.blueprint_exempt = set()
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
        self.swallow_errors = app.config.setdefault(
            C.SWALLOW_ERRORS, self.swallow_errors
        )
        self.headers_enabled = (
            self.headers_enabled
            or app.config.setdefault(C.HEADERS_ENABLED, False)
        )
        self.storage_options.update(
            app.config.get(C.STORAGE_OPTIONS, {})
        )
        self.storage = storage_from_string(
            self.storage_uri
            or app.config.setdefault(C.STORAGE_URL, 'memory://'),
            ** self.storage_options
        )
        strategy = (
            self.strategy
            or app.config.setdefault(C.STRATEGY, 'fixed-window')
        )
        if strategy not in STRATEGIES:
            raise ConfigurationError("Invalid rate limiting strategy %s" % strategy)
        self.limiter = STRATEGIES[strategy](self.storage)
        self.header_mapping.update({
           HEADERS.RESET : self.header_mapping.get(HEADERS.RESET,None) or app.config.setdefault(C.HEADER_RESET, "X-RateLimit-Reset"),
           HEADERS.REMAINING : self.header_mapping.get(HEADERS.REMAINING,None) or app.config.setdefault(C.HEADER_REMAINING, "X-RateLimit-Remaining"),
           HEADERS.LIMIT : self.header_mapping.get(HEADERS.LIMIT,None) or app.config.setdefault(C.HEADER_LIMIT, "X-RateLimit-Limit"),
        })

        conf_limits = app.config.get(C.GLOBAL_LIMITS, None)
        if not self.global_limits and conf_limits:
            self.global_limits = [
                ExtLimit(
                    limit, self.key_func, None, False, None, None
                ) for limit in parse_many(conf_limits)
            ]
        if self.auto_check:
            app.before_request(self.__check_request_limit)
        app.after_request(self.__inject_headers)

        # purely for backward compatibility as stated in flask documentation
        if not hasattr(app, 'extensions'):
            app.extensions = {} # pragma: no cover
        app.extensions['limiter'] = self

    def check(self):
        """
        check the limits for the current request

        :raises: RateLimitExceeded
        """
        self.__check_request_limit()

    def __inject_headers(self, response):
        current_limit = getattr(g, 'view_rate_limit', None)
        if self.enabled and self.headers_enabled and current_limit:
            window_stats = self.limiter.get_window_stats(*current_limit)
            response.headers.add(
                self.header_mapping[HEADERS.LIMIT],
                str(current_limit[0].amount)
            )
            response.headers.add(
                self.header_mapping[HEADERS.REMAINING],
                window_stats[1]
            )
            response.headers.add(
                self.header_mapping[HEADERS.RESET],
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
        if (not request.endpoint
            or not self.enabled
            or view_func == current_app.send_static_file
            or name in self.exempt_routes
            or request.blueprint in self.blueprint_exempt
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
                            limit, lim.key_func, lim.scope, lim.per_method,
                            lim.methods, lim.error_message
                        ) for limit in parse_many(lim.limit)
                    )
                except ValueError as e:
                    self.logger.error(
                        "failed to load ratelimit for view function %s (%s)"
                        , name, e
                    )
        if request.blueprint:
            if (request.blueprint in self.blueprint_dynamic_limits
                and not dynamic_limits
            ):
                for lim in self.blueprint_dynamic_limits[request.blueprint]:
                    try:
                        dynamic_limits.extend(
                            ExtLimit(
                                limit, lim.key_func, lim.scope, lim.per_method,
                                lim.methods, lim.error_message
                            ) for limit in parse_many(lim.limit)
                        )
                    except ValueError as e:
                        self.logger.error(
                            "failed to load ratelimit for blueprint %s (%s)"
                            , request.blueprint, e
                        )
            if (request.blueprint in self.blueprint_limits
                and not limits
            ):
               limits.extend(self.blueprint_limits[request.blueprint])

        failed_limit = None
        limit_for_header = None
        try:
            for lim in (limits + dynamic_limits or self.global_limits):
                limit_scope = lim.scope or endpoint
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
        except Exception: # no qa
            if self.swallow_errors:
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
                          error_message=None):
        _scope = scope if shared else None

        def _inner(obj):
            func = key_func or self.key_func
            is_route = not isinstance(obj, Blueprint)
            name = "%s.%s" % (obj.__module__, obj.__name__) if is_route else obj.name
            dynamic_limit, static_limits = None, []
            if callable(limit_value):
                dynamic_limit = ExtLimit(limit_value, func, _scope, per_method,
                                         methods, error_message)
            else:
                try:
                    static_limits = [ExtLimit(
                        limit, func, _scope, per_method,
                        methods, error_message
                    ) for limit in parse_many(limit_value)]
                except ValueError as e:
                    self.logger.error(
                        "failed to configure %s %s (%s)",
                        "view function" if is_route else "blueprint", name, e
                    )
            if isinstance(obj, Blueprint):
                if dynamic_limit:
                    self.blueprint_dynamic_limits.setdefault(name, []).append(
                        dynamic_limit
                    )
                else:
                    self.blueprint_limits.setdefault(name, []).extend(
                        static_limits
                    )
            else:
                @wraps(obj)
                def __inner(*a, **k):
                    return obj(*a, **k)
                if dynamic_limit:
                    self.dynamic_route_limits.setdefault(name, []).append(
                        dynamic_limit
                    )
                else:
                    self.route_limits.setdefault(name, []).extend(
                        static_limits
                    )
                return __inner
        return _inner


    def limit(self, limit_value, key_func=None, per_method=False,
              methods=None, error_message=None):
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
                                      methods=methods, error_message=error_message)


    def shared_limit(self, limit_value, scope, key_func=None,
                     error_message=None):
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
            limit_value, key_func, True, scope, error_message=error_message
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
            self.exempt_routes.add(name)
            return __inner
        else:
            self.blueprint_exempt.add(obj.name)

    def request_filter(self, fn):
        """
        decorator to mark a function as a filter to be executed
        to check if the request is exempt from rate limiting.
        """
        self.request_filters.append(fn)
        return fn

