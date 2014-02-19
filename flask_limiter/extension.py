"""
the flask extension
"""

from functools import wraps
import logging

from flask import request, current_app

from .errors import RateLimitExceeded, ConfigurationError
from .strategies import STRATEGIES
from .util import storage_from_string, parse_many, get_ipaddr

class Limiter(object):
    """
    :param app: :class:`flask.Flask` instance to initialize the extension
     with.
    :param list global_limits: a variable list of strings denoting global
     limits to apply to all routes. :ref:`ratelimit-string` for  more details.
    :param function key_func: a callable that returns the domain to rate limit by.
     Defaults to the remote address of the request.
    """

    def __init__(self, app=None, key_func=get_ipaddr, global_limits=[]):
        self.app = app
        self.enabled = True
        self.global_limits = []
        self.exempt_routes = []
        for limit in global_limits:
            self.global_limits.extend(
                [
                    (key_func, limit) for limit in parse_many(limit)
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
        self.enabled = app.config.setdefault("RATELIMIT_ENABLED", True)
        self.storage = storage_from_string(
            app.config.setdefault('RATELIMIT_STORAGE_URL', 'memory://')
        )
        strategy = app.config.setdefault('RATELIMIT_STRATEGY', 'fixed-window')
        if not strategy in STRATEGIES:
            raise ConfigurationError("Invalid rate limiting strategy %s" % strategy)
        self.limiter = STRATEGIES[strategy](self.storage)
        conf_limits = app.config.get("RATELIMIT_GLOBAL", None)
        if not self.global_limits and conf_limits:
            self.global_limits = [
                (self.key_func, limit) for limit in parse_many(conf_limits)
            ]
        app.before_request(self.__check_request_limit)

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
        ):
            return
        limits = (
            name in self.route_limits and self.route_limits[name]
            or []
        )
        dynamic_limits = []
        if name in self.dynamic_route_limits:
            for key_func, limit_func in self.dynamic_route_limits[name]:
                try:
                    dynamic_limits.extend(
                        [key_func, limit] for limit in parse_many(limit_func())
                    )
                except ValueError as e:
                    self.logger.error(
                        "failed to load ratelimit for view function %s (%s)" % (name, e)
                    )

        failed_limit = None
        for key_func, limit in (limits + dynamic_limits or self.global_limits):
            if not self.limiter.hit(limit, key_func(), endpoint):
                self.logger.warn(
                    "ratelimit %s (%s) exceeded at endpoint: %s" % (
                    limit, key_func(), endpoint))
                failed_limit = limit
        if failed_limit:
            raise RateLimitExceeded(failed_limit)

    def limit(self, limit_value, key_func=None):
        """
        decorator to be used for rate limiting specific routes.

        :param limit_value: rate limit string or a callable that returns a string.
         :ref:`ratelimit-string` for more details.
        :param key_func: function/lambda to extract the unique identifier for
         the rate limit. defaults to remote address of the request.
        :return:
        """

        def _inner(fn):
            name = "%s.%s" % (fn.__module__, fn.__name__)
            @wraps(fn)
            def __inner(*a, **k):
                return fn(*a, **k)
            func = key_func or self.key_func
            if callable(limit_value):
                self.dynamic_route_limits.setdefault(name, []).append(
                    (func, limit_value)
                )
            else:
                try:
                    self.route_limits.setdefault(name, []).extend(
                        [(func, limit) for limit in parse_many(limit_value)]
                    )
                except ValueError as e:
                    self.logger.error(
                        "failed to configure view function %s (%s)" % (name, e)
                    )

            return __inner
        return _inner

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
