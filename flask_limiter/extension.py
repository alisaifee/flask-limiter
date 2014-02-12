"""

"""
from functools import wraps
from flask import request, current_app

from .errors import RateLimitExceeded
from .limits import RateLimitManager
from .util import storage_from_string, parse_many, parse, get_ipaddr


class Limiter(object):
    """
    The flask extension to wrap the :class:`flask.Flask`
    """
    def __init__(self, app, **global_limits):
        self.app = app
        self.global_limits = [parse(limit) for limit in global_limits]
        self.route_limits = {}
        self.storage = self.limiter = None
        if app:
            self.init_app(app)

    def init_app(self, app):
        self.storage = storage_from_string(
            app.config.setdefault('RATELIMIT_STORAGE_URL', 'memory://')
        )
        self.limiter = RateLimitManager(self.storage)
        global_limit = app.config.get("RATELIMIT_GLOBAL", None)
        if global_limit:
            self.global_limits = [
                (get_ipaddr, limit) for limit in parse_many(global_limit)
            ]
        app.before_request(self.check_request_limit)

    def check_request_limit(self):
        endpoint = request.endpoint or ""
        view_func = current_app.view_functions.get(endpoint, None)
        name = ("%s.%s" % (
                view_func.__module__, view_func.__name__
            ) if view_func else ""
        )
        limits = (
            name in self.route_limits and self.route_limits[name]
            or self.global_limits
        )
        if not all([self.limiter.hit(l, k(), endpoint) for k, l in limits]):
            raise RateLimitExceeded()

    def limit(self, limit_string, key_func=get_ipaddr):
        def _inner(fn):
            name = "%s.%s" % (fn.__module__, fn.__name__)
            @wraps(fn)
            def __inner(*a, **k):
                return fn(*a, **k)
            self.route_limits.setdefault(name, [])
            self.route_limits[name].extend(
                [(key_func, limit) for limit in parse_many(limit_string)]
            )
            return __inner
        return _inner
