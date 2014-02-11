"""

"""
from functools import wraps
from flask import request, current_app
from flask.ext.ratelimits.errors import RateLimitException
from flask.ext.ratelimits.limits import Limiter
from flask.ext.ratelimits.util import storage_from_string, parse_many

class LimitCollection(list):
    def __init__(self, key_func, *args):
        super(LimitCollection, self).__init__(*args)
        self.key_func = key_func


def get_ipaddr():
    return request.remote_addr


class RateLimits(object):
    def __init__(self, app):
        self.app = app
        self.global_limits = []
        self.route_limits = {}
        self.storage = self.limiter = None
        if app:
            self.init_app(app)

    def init_app(self, app):
        self.storage = storage_from_string(
            app.config.setdefault('RATELIMIT_STORAGE_URL', 'memory://')
        )
        self.limiter = Limiter(self.storage)
        global_limit = app.config.get("RATELIMIT_GLOBAL", None)
        if global_limit:
            self.global_limits = LimitCollection(get_ipaddr, parse_many(global_limit))

        app.before_request(self.check_request_limit)

    def check_request_limit(self):
        addr = request.remote_addr or "127.0.0.1"
        endpoint = request.endpoint or ""
        view_func = current_app.view_functions.get(endpoint, None)
        limits = (
            view_func in self.route_limits and self.route_limits[view_func]
            or self.global_limits
        )
        if not all([self.limiter.hit(l, addr, endpoint) for l in limits]):
            raise RateLimitException()

    def limit(self, limit_string, key_func=get_ipaddr):
        def _inner(fn):
            @wraps(fn)
            def __inner(*a, **k):
                return fn(*a, **k)
            self.route_limits[__inner] = LimitCollection(key_func, parse_many(limit_string))
            return __inner
        return _inner
