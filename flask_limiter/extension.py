"""

"""
from functools import wraps
from flask import request, current_app, session

from .errors import RateLimitExceeded
from .limits import RateLimitManager
from .util import storage_from_string, parse_many, parse, get_ipaddr


class Limiter(object):
    """
    :param app: :class:`flask.Flask` instance to initialize the extension
     with.
    :param global_limits: a variable list of strings denoting global
     limits to apply to all routes.
    """

    def __init__(self, app=None, key_func=get_ipaddr, global_limits=[]):
        self.app = app
        self.global_limits = []
        for limit in global_limits:
            self.global_limits.extend(
                [
                    (key_func, limit) for limit in parse_many(limit)
                ]
            )
        self.route_limits = {}
        self.storage = self.limiter = None
        self.key_func = key_func
        if app:
            self.init_app(app)

    def init_app(self, app):
        """
        :param app: :class:`flask.Flask` instance to rate limit.
        """
        self.storage = storage_from_string(
            app.config.setdefault('RATELIMIT_STORAGE_URL', 'memory://')
        )
        self.limiter = RateLimitManager(self.storage)
        conf_limits = app.config.get("RATELIMIT_GLOBAL", None)
        if not self.global_limits and conf_limits:
            self.global_limits = [
                (self.key_func, limit) for limit in parse_many(conf_limits)
            ]
        app.before_request(self.__check_request_limit)

    def __check_request_limit(self):
        endpoint = request.endpoint or ""
        view_func = current_app.view_functions.get(endpoint, None)
        if view_func == current_app.send_static_file:
            return
        name = ("%s.%s" % (
                view_func.__module__, view_func.__name__
            ) if view_func else ""
        )
        limits = (
            name in self.route_limits and self.route_limits[name]
            or self.global_limits
        )
        failed_limit = None
        for key_func, limit in limits:
            if not self.limiter.hit(limit, key_func(), endpoint):
                current_app.logger.info(
                    "ratelimit %s (%s) exceeded at endpoint: %s" % (
                    limit, key_func(), endpoint))
                failed_limit = limit
        if failed_limit:
            raise RateLimitExceeded(failed_limit)

    def limit(self, limit_string, key_func=None):
        """
        decorator to be used for rate limiting specific routes.

        :param limit_string: rate limit string(s) refer to :ref:`ratelimit-string`
        :param key_func: function/lambda to extract the unique identifier for
         the rate limit. defaults to remote address of the request.
        :return:
        """

        def _inner(fn):
            name = "%s.%s" % (fn.__module__, fn.__name__)
            @wraps(fn)
            def __inner(*a, **k):
                return fn(*a, **k)
            self.route_limits.setdefault(name, [])
            self.route_limits[name].extend(
                [(key_func or self.key_func, limit) for limit in parse_many(limit_string)]
            )
            return __inner
        return _inner
