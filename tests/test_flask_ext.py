"""

"""
import json
import logging
import time
from functools import wraps

import functools
import hiro
import mock
from flask import Flask, Blueprint, request, current_app, make_response, g
from flask_restful import Resource, Api as RestfulApi
from flask.views import View, MethodView
from limits.errors import ConfigurationError
from limits.storage import MemcachedStorage
from limits.strategies import MovingWindowRateLimiter
from werkzeug.exceptions import BadRequest

from flask_limiter.extension import C, Limiter, HEADERS
from flask_limiter.util import get_remote_address, get_ipaddr
from tests import FlaskLimiterTestCase
import pytest


class ConfigurationTests(FlaskLimiterTestCase):
    def test_invalid_strategy(self):
        app = Flask(__name__)
        app.config.setdefault(C.STRATEGY, "fubar")
        with pytest.raises(ConfigurationError):
            Limiter(app, key_func=get_remote_address)

    def test_invalid_storage_string(self):
        app = Flask(__name__)
        app.config.setdefault(C.STORAGE_URL, "fubar://localhost:1234")
        with pytest.raises(ConfigurationError):
            Limiter(app, key_func=get_remote_address)

    def test_constructor_arguments_over_config(self):
        app = Flask(__name__)
        app.config.setdefault(C.STRATEGY, "fixed-window-elastic-expiry")
        limiter = Limiter(
            strategy='moving-window', key_func=get_remote_address
        )
        limiter.init_app(app)
        app.config.setdefault(C.STORAGE_URL, "redis://localhost:36379")
        assert type(limiter._limiter) == MovingWindowRateLimiter
        limiter = Limiter(
            storage_uri='memcached://localhost:31211',
            key_func=get_remote_address
        )
        limiter.init_app(app)
        assert type(limiter._storage) == MemcachedStorage


class ErrorHandlingTests(FlaskLimiterTestCase):
    def test_error_message(self):
        app, limiter = self.build_app({C.GLOBAL_LIMITS: "1 per day"})

        @app.route("/")
        def null():
            return ""

        with app.test_client() as cli:
            cli.get("/")
            assert "1 per 1 day" in cli.get("/").data.decode()

            @app.errorhandler(429)
            def ratelimit_handler(e):
                return make_response(
                    '{"error" : "rate limit %s"}' % str(e.description), 429
                )

            assert {
                'error': 'rate limit 1 per 1 day'
            } == json.loads(cli.get("/").data.decode())

    def test_custom_error_message(self):
        app, limiter = self.build_app()

        @app.errorhandler(429)
        def ratelimit_handler(e):
            return make_response(e.description, 429)

        def l1():
            return "1/second"

        def e1():
            return "dos"

        @app.route("/t1")
        @limiter.limit("1/second", error_message="uno")
        def t1():
            return "1"

        @app.route("/t2")
        @limiter.limit(l1, error_message=e1)
        def t2():
            return "2"

        s1 = limiter.shared_limit(
            "1/second", scope='error_message', error_message="tres"
        )

        @app.route("/t3")
        @s1
        def t3():
            return "3"

        with hiro.Timeline().freeze():
            with app.test_client() as cli:
                cli.get("/t1")
                resp = cli.get("/t1")
                assert 429 == resp.status_code
                assert resp.data == b'uno'
                cli.get("/t2")
                resp = cli.get("/t2")
                assert 429 == resp.status_code
                assert resp.data == b'dos'
                cli.get("/t3")
                resp = cli.get("/t3")
                assert 429 == resp.status_code
                assert resp.data == b'tres'

    def test_swallow_error(self):
        app, limiter = self.build_app({
            C.GLOBAL_LIMITS: "1 per day",
            C.HEADERS_ENABLED: True,
            C.SWALLOW_ERRORS: True,
        })

        @app.route("/")
        def null():
            return "ok"

        with app.test_client() as cli:
            with mock.patch(
                "limits.strategies.FixedWindowRateLimiter.hit"
            ) as hit:

                def raiser(*a, **k):
                    raise Exception

                hit.side_effect = raiser
                assert "ok" in cli.get("/").data.decode()
            with mock.patch(
                    "limits.strategies.FixedWindowRateLimiter.get_window_stats"
            ) as get_window_stats:

                def raiser(*a, **k):
                    raise Exception

                get_window_stats.side_effect = raiser
                assert "ok" in cli.get("/").data.decode()

    def test_no_swallow_error(self):
        app, limiter = self.build_app({
            C.GLOBAL_LIMITS: "1 per day",
            C.HEADERS_ENABLED: True
        })

        @app.route("/")
        def null():
            return "ok"

        @app.errorhandler(500)
        def e500(e):
            return str(e.original_exception), 500

        def raiser(*a, **k):
            raise Exception("underlying")

        with app.test_client() as cli:
            with mock.patch(
                "limits.strategies.FixedWindowRateLimiter.hit"
            ) as hit:

                hit.side_effect = raiser
                assert 500 == cli.get("/").status_code
                assert "underlying" == cli.get("/").data.decode()
            with mock.patch(
                "limits.strategies.FixedWindowRateLimiter.get_window_stats"
            ) as get_window_stats:

                get_window_stats.side_effect = raiser
                assert 500 == cli.get("/").status_code
                assert "underlying" == cli.get("/").data.decode()

    def test_fallback_to_memory_config(self):
        _, limiter = self.build_app(
            config={C.ENABLED: True},
            default_limits=["5/minute"],
            storage_uri="redis://localhost:36379",
            in_memory_fallback=["1/minute"]
        )
        assert len(limiter._in_memory_fallback) == 1
        assert limiter._in_memory_fallback_enabled

        _, limiter = self.build_app(
            config={C.ENABLED: True,
                    C.IN_MEMORY_FALLBACK: "1/minute"},
            default_limits=["5/minute"],
            storage_uri="redis://localhost:36379",
        )
        assert len(limiter._in_memory_fallback) == 1
        assert limiter._in_memory_fallback_enabled

        _, limiter = self.build_app(
            config={C.ENABLED: True, C.IN_MEMORY_FALLBACK_ENABLED: True},
            global_limits=["5/minute"],
            storage_uri="redis://localhost:36379",
        )
        assert limiter._in_memory_fallback_enabled

        _, limiter = self.build_app(
            config={C.ENABLED: True},
            global_limits=["5/minute"],
            storage_uri="redis://localhost:36379",
            in_memory_fallback_enabled=True
        )

    def test_fallback_to_memory_backoff_check(self):
        app, limiter = self.build_app(
            config={C.ENABLED: True},
            default_limits=["5/minute"],
            storage_uri="redis://localhost:36379",
            in_memory_fallback=["1/minute"]
        )

        @app.route("/t1")
        def t1():
            return "test"

        with app.test_client() as cli:

            def raiser(*a):
                raise Exception("redis dead")

            with hiro.Timeline() as timeline:
                with mock.patch(
                    'limits.storage.RedisStorage.incr'
                ) as incr:
                    with mock.patch(
                            'limits.storage.RedisStorage.check'
                    ) as check:
                        check.return_value = False
                        incr.side_effect = raiser
                        assert cli.get("/t1").status_code == 200
                        assert cli.get("/t1").status_code == 429
                        timeline.forward(1)
                        assert cli.get("/t1").status_code == 429
                        timeline.forward(2)
                        assert cli.get("/t1").status_code == 429
                        timeline.forward(4)
                        assert cli.get("/t1").status_code == 429
                        timeline.forward(8)
                        assert cli.get("/t1").status_code == 429
                        timeline.forward(16)
                        assert cli.get("/t1").status_code == 429
                        timeline.forward(32)
                        assert cli.get("/t1").status_code == 200
                # redis back to normal, but exponential backoff will only
                # result in it being marked after pow(2,0) seconds and next
                # check
                assert cli.get("/t1").status_code == 429
                timeline.forward(2)
                assert cli.get("/t1").status_code == 200
                assert cli.get("/t1").status_code == 200
                assert cli.get("/t1").status_code == 200
                assert cli.get("/t1").status_code == 200
                assert cli.get("/t1").status_code == 200
                assert cli.get("/t1").status_code == 429

    def test_fallback_to_memory_with_global_override(self):
        app, limiter = self.build_app(
            config={C.ENABLED: True},
            default_limits=["5/minute"],
            storage_uri="redis://localhost:36379",
            in_memory_fallback=["1/minute"]
        )

        @app.route("/t1")
        def t1():
            return "test"

        @app.route("/t2")
        @limiter.limit("3 per minute")
        def t2():
            return "test"

        with app.test_client() as cli:
            assert cli.get("/t1").status_code == 200
            assert cli.get("/t1").status_code == 200
            assert cli.get("/t1").status_code == 200
            assert cli.get("/t1").status_code == 200
            assert cli.get("/t1").status_code == 200
            assert cli.get("/t1").status_code == 429
            assert cli.get("/t2").status_code == 200
            assert cli.get("/t2").status_code == 200
            assert cli.get("/t2").status_code == 200
            assert cli.get("/t2").status_code == 429

            def raiser(*a):
                raise Exception("redis dead")

            with mock.patch(
                'limits.storage.RedisStorage.incr'
            ) as incr:
                with mock.patch('limits.storage.RedisStorage.check') as check:
                    check.return_value = False
                    incr.side_effect = raiser
                    assert cli.get("/t1").status_code == 200
                    assert cli.get("/t1").status_code == 429
                    assert cli.get("/t2").status_code == 200
                    assert cli.get("/t2").status_code == 429
            # redis back to normal, go back to regular limits
            with hiro.Timeline() as timeline:
                timeline.forward(2)
                limiter._storage.storage.flushall()
                assert cli.get("/t2").status_code == 200
                assert cli.get("/t2").status_code == 200
                assert cli.get("/t2").status_code == 200
                assert cli.get("/t2").status_code == 429

    def test_fallback_to_memory(self):
        app, limiter = self.build_app(
            config={C.ENABLED: True},
            global_limits=["2/minute"],
            storage_uri="redis://localhost:36379",
            in_memory_fallback_enabled=True,
            headers_enabled=True
        )

        @app.route("/t1")
        def t1():
            return "test"

        @app.route("/t2")
        @limiter.limit("1 per minute")
        def t2():
            return "test"
        with app.test_client() as cli:
            assert cli.get("/t1").status_code == 200
            assert cli.get("/t1").status_code == 200
            assert cli.get("/t1").status_code == 429
            assert cli.get("/t2").status_code == 200
            assert cli.get("/t2").status_code == 429

            def raiser(*a):
                raise Exception("redis dead")

            with mock.patch(
                'limits.storage.RedisStorage.incr'
            ) as hit:
                hit.side_effect = raiser
                assert cli.get("/t1").status_code == 200
                assert cli.get("/t1").status_code == 200
                assert cli.get("/t1").status_code == 429
                assert cli.get("/t2").status_code == 200
                assert cli.get("/t2").status_code == 429
            with hiro.Timeline() as timeline:
                timeline.forward(1)
                limiter._storage.storage.flushall()
                assert cli.get("/t2").status_code == 200
                assert cli.get("/t2").status_code == 429
            with mock.patch(
                'limits.storage.RedisStorage.get'
            ) as get:
                get.side_effect = raiser
                assert cli.get("/t1").status_code == 200


class DecoratorTests(FlaskLimiterTestCase):
    def test_multiple_decorators(self):
        app, limiter = self.build_app(key_func=get_ipaddr)

        @app.route("/t1")
        @limiter.limit(
            "100 per minute", lambda: "test"
        )  # effectively becomes a limit for all users
        @limiter.limit("50/minute")  # per ip as per default key_func
        def t1():
            return "test"

        with hiro.Timeline().freeze():
            with app.test_client() as cli:
                for i in range(0, 100):
                    assert (200 if i < 50 else 429) == cli.get(
                        "/t1", headers={
                            "X_FORWARDED_FOR": "127.0.0.2"
                        }
                    ).status_code
                for i in range(50):
                    assert 200 == cli.get("/t1").status_code
                assert 429 == cli.get("/t1").status_code
                assert 429 == \
                    cli.get("/t1", headers={
                        "X_FORWARDED_FOR": "127.0.0.3"
                    }).status_code

    def test_exempt_routes(self):
        app, limiter = self.build_app(default_limits=["1/minute"])

        @app.route("/t1")
        def t1():
            return "test"

        @app.route("/t2")
        @limiter.exempt
        def t2():
            return "test"

        with app.test_client() as cli:
            assert cli.get("/t1").status_code == 200
            assert cli.get("/t1").status_code == 429
            assert cli.get("/t2").status_code == 200
            assert cli.get("/t2").status_code == 200

    def test_decorated_limit_with_conditional_deduction(self):
        app, limiter = self.build_app()

        @app.route("/t/<path:path>")
        @limiter.limit(
            "1/second", deduct_when=lambda resp: resp.status_code == 200
        )
        @limiter.limit(
            "1/minute", deduct_when=lambda resp: resp.status_code == 400
        )
        def t(path):
            if path == "1":
                return "test"
            raise BadRequest()

        with hiro.Timeline() as timeline:
            with app.test_client() as cli:
                assert cli.get("/t/1").status_code == 200
                assert cli.get("/t/1").status_code == 429
                timeline.forward(1)
                assert cli.get("/t/2").status_code == 400
                timeline.forward(1)
                assert cli.get("/t/1").status_code == 429
                assert cli.get("/t/2").status_code == 429
                timeline.forward(60)
                assert cli.get("/t/1").status_code == 200

    def test_shared_limit_with_conditional_deduction(self):
        app, limiter = self.build_app()

        bp = Blueprint("main", __name__)

        limit = limiter.shared_limit(
            "2/minute", "not_found",
            deduct_when=lambda response: response.status_code == 400
        )

        @app.route("/test/<path:path>")
        @limit
        def app_test(path):
            if path != "1":
                raise BadRequest()
            return path

        @bp.route("/test/<path:path>")
        def bp_test(path):
            if path != "1":
                raise BadRequest()
            return path

        limit(bp)

        app.register_blueprint(bp, url_prefix='/bp')

        with hiro.Timeline() as timeline:
            with app.test_client() as cli:
                assert cli.get("/bp/test/1").status_code == 200
                assert cli.get("/bp/test/1").status_code == 200
                assert cli.get("/test/1").status_code == 200
                assert cli.get("/bp/test/2").status_code == 400
                assert cli.get("/test/2").status_code == 400
                assert cli.get("/bp/test/2").status_code == 429
                assert cli.get("/bp/test/1").status_code == 429
                assert cli.get("/test/1").status_code == 429
                assert cli.get("/test/2").status_code == 429
                timeline.forward(60)
                assert cli.get("/bp/test/1").status_code == 200
                assert cli.get("/test/1").status_code == 200

    def test_header_ordering_with_conditional_deductions(self):
        app, limiter = self.build_app(
            default_limits=['3/second'], headers_enabled=True
        )

        @app.route("/test_combined/<path:path>")
        @limiter.limit(
            "1/hour", override_defaults=False,
            deduct_when=lambda response: response.status_code != 200
        )
        @limiter.limit(
            "4/minute", override_defaults=False,
            deduct_when=lambda response: response.status_code == 200
        )
        def app_test_combined(path):
            if path != "1":
                raise BadRequest()
            return path

        @app.route("/test/<path:path>")
        @limiter.limit(
            "2/hour", deduct_when=lambda response: response.status_code != 200
        )
        def app_test(path):
            if path != "1":
                raise BadRequest()
            return path

        with hiro.Timeline() as timeline:
            with app.test_client() as cli:
                assert cli.get("/test_combined/1").status_code == 200
                resp = cli.get("/test_combined/1")
                assert resp.status_code == 200
                assert resp.headers.get('X-RateLimit-Limit') == '3'
                assert resp.headers.get('X-RateLimit-Remaining') == '1'
                assert cli.get("/test_combined/2").status_code == 400

                resp = cli.get("/test/1")
                assert resp.headers.get('X-RateLimit-Limit') is None
                resp = cli.get("/test/2")
                assert resp.headers.get('X-RateLimit-Limit') == '2'
                assert resp.headers.get('X-RateLimit-Remaining') == '1'

                resp = cli.get("/test_combined/1")
                assert resp.status_code == 429
                assert resp.headers.get('X-RateLimit-Limit') == '1'
                assert resp.headers.get('X-RateLimit-Remaining') == '0'
                assert cli.get("/test_combined/2").status_code == 429
                timeline.forward(60)
                assert cli.get("/test_combined/1").status_code == 429
                assert cli.get("/test_combined/2").status_code == 429
                timeline.forward(3600)
                assert cli.get("/test_combined/1").status_code == 200

    def test_decorated_limits_with_combined_defaults(self):
        app, limiter = self.build_app(
            default_limits=['2/minute']
        )

        @app.route("/")
        @limiter.limit("1/second", override_defaults=False)
        def root():
            return "root"

        with hiro.Timeline() as timeline:
            with app.test_client() as cli:
                assert 200 == cli.get("/").status_code
                assert 429 == cli.get("/").status_code
                timeline.forward(60)
                assert 200 == cli.get("/").status_code
                timeline.forward(1)
                assert 200 == cli.get("/").status_code
                timeline.forward(1)
                assert 429 == cli.get("/").status_code

    def test_decorated_limit_with_combined_defaults_per_method(self):
        app, limiter = self.build_app(
            default_limits=['2/minute'],
            default_limits_per_method=True
        )

        @app.route("/", methods=['GET', 'PUT'])
        @limiter.limit("1/second", override_defaults=False, methods=['GET'])
        def root():
            return "root"

        with hiro.Timeline() as timeline:
            with app.test_client() as cli:
                assert 200 == cli.get("/").status_code
                assert 429 == cli.get("/").status_code
                assert 200 == cli.put("/").status_code
                assert 200 == cli.put("/").status_code
                assert 429 == cli.put("/").status_code
                timeline.forward(60)
                assert 200 == cli.get("/").status_code
                assert 200 == cli.put("/").status_code
                timeline.forward(1)
                assert 200 == cli.get("/").status_code
                assert 200 == cli.put("/").status_code
                timeline.forward(1)
                assert 429 == cli.get("/").status_code
                assert 429 == cli.put("/").status_code

    def test_decorated_dynamic_limits(self):
        app, limiter = self.build_app(
            {"X": "2 per second"}, default_limits=["1/second"]
        )

        def request_context_limit():
            limits = {
                "127.0.0.1": "10 per minute",
                "127.0.0.2": "1 per minute"
            }
            remote_addr = (request.access_route and request.access_route[0]
                           ) or request.remote_addr or '127.0.0.1'
            limit = limits.setdefault(remote_addr, '1 per minute')
            return limit

        @app.route("/t1")
        @limiter.limit("20/day")
        @limiter.limit(lambda: current_app.config.get("X"))
        @limiter.limit(request_context_limit)
        def t1():
            return "42"

        @app.route("/t2")
        @limiter.limit(lambda: current_app.config.get("X"))
        def t2():
            return "42"

        R1 = {"X_FORWARDED_FOR": "127.0.0.1, 127.0.0.0"}
        R2 = {"X_FORWARDED_FOR": "127.0.0.2"}

        with app.test_client() as cli:
            with hiro.Timeline().freeze() as timeline:
                for i in range(0, 10):
                    assert cli.get("/t1", headers=R1).status_code == 200
                    timeline.forward(1)
                assert cli.get("/t1", headers=R1).status_code == 429
                assert cli.get("/t1", headers=R2).status_code == 200
                assert cli.get("/t1", headers=R2).status_code == 429
                timeline.forward(60)
                assert cli.get("/t1", headers=R2).status_code == 200
                assert cli.get("/t2").status_code == 200
                assert cli.get("/t2").status_code == 200
                assert cli.get("/t2").status_code == 429
                timeline.forward(1)
                assert cli.get("/t2").status_code == 200

    def test_invalid_decorated_dynamic_limits(self, caplog):
        app = Flask(__name__)
        app.config.setdefault("X", "2 per sec")
        limiter = Limiter(
            app, default_limits=["1/second"], key_func=get_remote_address
        )

        @app.route("/t1")
        @limiter.limit(lambda: current_app.config.get("X"))
        def t1():
            return "42"

        with app.test_client() as cli:
            with hiro.Timeline().freeze():
                assert cli.get("/t1").status_code == 200
                assert cli.get("/t1").status_code == 429
        # 2 for invalid limit, 1 for warning.
        assert len(caplog.records) == 3
        assert (
            "failed to load ratelimit"
            in caplog.records[0].msg
        )
        assert (
            "failed to load ratelimit"
            in caplog.records[1].msg
        )
        assert (
            "exceeded at endpoint"
            in caplog.records[2].msg
        )
        assert caplog.records[2].levelname == 'WARNING'

    def test_invalid_decorated_static_limits(self, caplog):
        app = Flask(__name__)
        limiter = Limiter(
            app, default_limits=["1/second"], key_func=get_remote_address
        )

        @app.route("/t1")
        @limiter.limit("2/sec")
        def t1():
            return "42"

        with app.test_client() as cli:
            with hiro.Timeline().freeze():
                assert cli.get("/t1").status_code == 200
                assert cli.get("/t1").status_code == 429
        assert (
            "failed to configure"
            in caplog.records[0].msg
        )
        assert (
            "exceeded at endpoint"
            in caplog.records[1].msg
        )

    def test_named_shared_limit(self):
        app, limiter = self.build_app()
        shared_limit_a = limiter.shared_limit("1/minute", scope='a')
        shared_limit_b = limiter.shared_limit("1/minute", scope='b')

        @app.route("/t1")
        @shared_limit_a
        def route1():
            return "route1"

        @app.route("/t2")
        @shared_limit_a
        def route2():
            return "route2"

        @app.route("/t3")
        @shared_limit_b
        def route3():
            return "route3"

        with hiro.Timeline().freeze():
            with app.test_client() as cli:
                assert 200 == cli.get("/t1").status_code
                assert 200 == cli.get("/t3").status_code
                assert 429 == cli.get("/t2").status_code

    def test_dynamic_shared_limit(self):
        app, limiter = self.build_app()
        fn_a = mock.Mock()
        fn_b = mock.Mock()
        fn_a.return_value = "foo"
        fn_b.return_value = "bar"

        dy_limit_a = limiter.shared_limit("1/minute", scope=fn_a)
        dy_limit_b = limiter.shared_limit("1/minute", scope=fn_b)

        @app.route("/t1")
        @dy_limit_a
        def t1():
            return "route1"

        @app.route("/t2")
        @dy_limit_a
        def t2():
            return "route2"

        @app.route("/t3")
        @dy_limit_b
        def t3():
            return "route3"

        with hiro.Timeline().freeze():
            with app.test_client() as cli:
                assert 200 == cli.get("/t1").status_code
                assert 200 == cli.get("/t3").status_code
                assert 429 == cli.get("/t2").status_code
                assert 429 == cli.get("/t3").status_code
                assert 2 == fn_a.call_count
                assert 2 == fn_b.call_count
                fn_b.assert_called_with("t3")
                fn_a.assert_has_calls([mock.call("t1"), mock.call("t2")])

    def test_conditional_limits(self):
        """Test that the conditional activation of the limits work."""
        app = Flask(__name__)
        limiter = Limiter(app, key_func=get_remote_address)

        @app.route("/limited")
        @limiter.limit("1 per day")
        def limited_route():
            return "passed"

        @app.route("/unlimited")
        @limiter.limit("1 per day", exempt_when=lambda: True)
        def never_limited_route():
            return "should always pass"

        is_exempt = False

        @app.route("/conditional")
        @limiter.limit("1 per day", exempt_when=lambda: is_exempt)
        def conditionally_limited_route():
            return "conditional"

        with app.test_client() as cli:
            assert cli.get("/limited").status_code == 200
            assert cli.get("/limited").status_code == 429

            assert cli.get("/unlimited").status_code == 200
            assert cli.get("/unlimited").status_code == 200

            assert cli.get("/conditional").status_code == 200
            assert cli.get("/conditional").status_code == 429
            is_exempt = True
            assert cli.get("/conditional").status_code == 200
            is_exempt = False
            assert cli.get("/conditional").status_code == 429

    def test_conditional_shared_limits(self):
        """Test that conditional shared limits work."""
        app = Flask(__name__)
        limiter = Limiter(app, key_func=get_remote_address)

        @app.route("/limited")
        @limiter.shared_limit("1 per day", "test_scope")
        def limited_route():
            return "passed"

        @app.route("/unlimited")
        @limiter.shared_limit(
            "1 per day", "test_scope", exempt_when=lambda: True
        )
        def never_limited_route():
            return "should always pass"

        is_exempt = False

        @app.route("/conditional")
        @limiter.shared_limit(
            "1 per day", "test_scope", exempt_when=lambda: is_exempt
        )
        def conditionally_limited_route():
            return "conditional"

        with app.test_client() as cli:
            assert cli.get("/unlimited").status_code == 200
            assert cli.get("/unlimited").status_code == 200

            assert cli.get("/limited").status_code == 200
            assert cli.get("/limited").status_code == 429

            assert cli.get("/conditional").status_code == 429
            is_exempt = True
            assert cli.get("/conditional").status_code == 200
            is_exempt = False
            assert cli.get("/conditional").status_code == 429

    def test_whitelisting(self):

        app = Flask(__name__)
        limiter = Limiter(
            app,
            default_limits=["1/minute"],
            headers_enabled=True,
            key_func=get_remote_address
        )

        @app.route("/")
        def t():
            return "test"

        @limiter.request_filter
        def w():
            if request.headers.get("internal", None) == "true":
                return True
            return False

        with hiro.Timeline().freeze() as timeline:
            with app.test_client() as cli:
                assert cli.get("/").status_code == 200
                assert cli.get("/").status_code == 429
                timeline.forward(60)
                assert cli.get("/").status_code == 200

                for i in range(0, 10):
                    assert cli.get(
                        "/", headers={"internal": "true"}
                    ).status_code == 200

    def test_separate_method_limits(self):
        app, limiter = self.build_app()

        @limiter.limit("1/second", per_method=True)
        @app.route("/", methods=["GET", "POST"])
        def root():
            return "root"

        with hiro.Timeline():
            with app.test_client() as cli:
                assert 200 == cli.get("/").status_code
                assert 429 == cli.get("/").status_code
                assert 200 == cli.post("/").status_code
                assert 429 == cli.post("/").status_code

    def test_explicit_method_limits(self):
        app, limiter = self.build_app(default_limits=['2/second'])

        @app.route("/", methods=["GET", "POST"])
        @limiter.limit("1/second", methods=["GET"])
        def root():
            return "root"

        with hiro.Timeline():
            with app.test_client() as cli:
                assert 200 == cli.get("/").status_code
                assert 429 == cli.get("/").status_code
                assert 200 == cli.post("/").status_code
                assert 200 == cli.post("/").status_code
                assert 429 == cli.post("/").status_code

    def test_decorated_limit_immediate(self):
        app, limiter = self.build_app(default_limits=["1/minute"])

        def append_info(fn):
            @wraps(fn)
            def __inner(*args, **kwargs):
                g.rate_limit = "2/minute"
                return fn(*args, **kwargs)
            return __inner

        @app.route("/", methods=["GET", "POST"])
        @append_info
        @limiter.limit(lambda: g.rate_limit, per_method=True)
        def root():
            return "root"

        with hiro.Timeline().freeze():
            with app.test_client() as cli:
                assert 200 == cli.get("/").status_code
                assert 200 == cli.get("/").status_code
                assert 429 == cli.get("/").status_code

    def test_decorated_shared_limit_immediate(self):

        app, limiter = self.build_app(default_limits=['1/minute'])
        shared = limiter.shared_limit(lambda: g.rate_limit, 'shared')

        def append_info(fn):
            @wraps(fn)
            def __inner(*args, **kwargs):
                g.rate_limit = "2/minute"
                return fn(*args, **kwargs)
            return __inner

        @app.route("/", methods=["GET", "POST"])
        @append_info
        @shared
        def root():
            return "root"

        @app.route("/other", methods=["GET", "POST"])
        def other():
            return "other"

        with hiro.Timeline().freeze():
            with app.test_client() as cli:
                assert 200 == cli.get("/other").status_code
                assert 429 == cli.get("/other").status_code
                assert 200 == cli.get("/").status_code
                assert 200 == cli.get("/").status_code
                assert 429 == cli.get("/").status_code

    def test_backward_compatibility_with_incorrect_ordering(self):
        app, limiter = self.build_app()

        def something_else(fn):
            @functools.wraps(fn)
            def __inner(*args, **kwargs):
                return fn(*args, **kwargs)
            return __inner

        @limiter.limit("1/second")
        @app.route("/t1", methods=["GET", "POST"])
        def root():
            return "t1"

        @limiter.limit("1/second")
        @app.route("/t2", methods=["GET", "POST"])
        @something_else
        def t2():
            return "t2"

        @limiter.limit("2/second")
        @limiter.limit("1/second")
        @app.route("/t3", methods=["GET", "POST"])
        def t3():
            return "t3"

        with hiro.Timeline().freeze():
            with app.test_client() as cli:
                assert 200 == cli.get("/t1").status_code
                assert 429 == cli.get("/t1").status_code
                assert 200 == cli.get("/t2").status_code
                assert 429 == cli.get("/t2").status_code
                assert 200 == cli.get("/t3").status_code
                assert 429 == cli.get("/t3").status_code


class BlueprintTests(FlaskLimiterTestCase):
    def test_blueprint(self):
        app, limiter = self.build_app(default_limits=["1/minute"])
        bp = Blueprint("main", __name__)

        @bp.route("/t1")
        def t1():
            return "test"

        @bp.route("/t2")
        @limiter.limit("10 per minute")
        def t2():
            return "test"

        app.register_blueprint(bp)

        with app.test_client() as cli:
            assert cli.get("/t1").status_code == 200
            assert cli.get("/t1").status_code == 429
            for i in range(0, 10):
                assert cli.get("/t2").status_code == 200
            assert cli.get("/t2").status_code == 429

    def test_register_blueprint(self):
        app, limiter = self.build_app(default_limits=["1/minute"])
        bp_1 = Blueprint("bp1", __name__)
        bp_2 = Blueprint("bp2", __name__)
        bp_3 = Blueprint("bp3", __name__)
        bp_4 = Blueprint("bp4", __name__)

        @bp_1.route("/t1")
        def t1():
            return "test"

        @bp_1.route("/t2")
        def t2():
            return "test"

        @bp_2.route("/t3")
        def t3():
            return "test"

        @bp_3.route("/t4")
        def t4():
            return "test"

        @bp_4.route("/t5")
        def t5():
            return "test"

        def dy_limit():
            return "1/second"

        app.register_blueprint(bp_1)
        app.register_blueprint(bp_2)
        app.register_blueprint(bp_3)
        app.register_blueprint(bp_4)

        limiter.limit("1/second")(bp_1)
        limiter.exempt(bp_3)
        limiter.limit(dy_limit)(bp_4)

        with hiro.Timeline().freeze() as timeline:
            with app.test_client() as cli:
                assert cli.get("/t1").status_code == 200
                assert cli.get("/t1").status_code == 429
                timeline.forward(1)
                assert cli.get("/t1").status_code == 200
                assert cli.get("/t2").status_code == 200
                assert cli.get("/t2").status_code == 429
                timeline.forward(1)
                assert cli.get("/t2").status_code == 200

                assert cli.get("/t3").status_code == 200
                for i in range(0, 10):
                    timeline.forward(1)
                    assert cli.get("/t3").status_code == 429

                for i in range(0, 10):
                    assert cli.get("/t4").status_code == 200

                assert cli.get("/t5").status_code == 200
                assert cli.get("/t5").status_code == 429

    def test_invalid_decorated_static_limit_blueprint(self, caplog):
        app = Flask(__name__)
        limiter = Limiter(
            app, default_limits=["1/second"], key_func=get_remote_address
        )
        bp = Blueprint("bp1", __name__)

        @bp.route("/t1")
        def t1():
            return "42"

        limiter.limit("2/sec")(bp)
        app.register_blueprint(bp)

        with app.test_client() as cli:
            with hiro.Timeline().freeze():
                assert cli.get("/t1").status_code == 200
                assert cli.get("/t1").status_code == 429
        assert (
            "failed to configure"
            in caplog.records[0].msg
        )
        assert (
            "exceeded at endpoint"
            in caplog.records[1].msg
        )

    def test_invalid_decorated_dynamic_limits_blueprint(self, caplog):
        app = Flask(__name__)
        app.config.setdefault("X", "2 per sec")
        limiter = Limiter(
            app, default_limits=["1/second"], key_func=get_remote_address
        )
        bp = Blueprint("bp1", __name__)

        @bp.route("/t1")
        def t1():
            return "42"

        limiter.limit(lambda: current_app.config.get("X"))(bp)
        app.register_blueprint(bp)

        with app.test_client() as cli:
            with hiro.Timeline().freeze():
                assert cli.get("/t1").status_code == 200
                assert cli.get("/t1").status_code == 429

        assert len(caplog.records) == 3
        assert "failed to load ratelimit" in caplog.records[0].msg
        assert "failed to load ratelimit" in caplog.records[1].msg
        assert "exceeded at endpoint" in caplog.records[2].msg


class ViewsTests(FlaskLimiterTestCase):
    def test_pluggable_views(self):
        app, limiter = self.build_app(default_limits=["1/hour"])

        class Va(View):
            methods = ['GET', 'POST']
            decorators = [limiter.limit("2/second")]

            def dispatch_request(self):
                return request.method.lower()

        class Vb(View):
            methods = ['GET']
            decorators = [limiter.limit("1/second, 3/minute")]

            def dispatch_request(self):
                return request.method.lower()

        class Vc(View):
            methods = ['GET']

            def dispatch_request(self):
                return request.method.lower()

        app.add_url_rule("/a", view_func=Va.as_view("a"))
        app.add_url_rule("/b", view_func=Vb.as_view("b"))
        app.add_url_rule("/c", view_func=Vc.as_view("c"))
        with hiro.Timeline().freeze() as timeline:
            with app.test_client() as cli:
                assert 200 == cli.get("/a").status_code
                assert 200 == cli.get("/a").status_code
                assert 429 == cli.post("/a").status_code
                assert 200 == cli.get("/b").status_code
                timeline.forward(1)
                assert 200 == cli.get("/b").status_code
                timeline.forward(1)
                assert 200 == cli.get("/b").status_code
                timeline.forward(1)
                assert 429 == cli.get("/b").status_code
                assert 200 == cli.get("/c").status_code
                assert 429 == cli.get("/c").status_code

    def test_pluggable_method_views(self):
        app, limiter = self.build_app(default_limits=["1/hour"])

        class Va(MethodView):
            decorators = [limiter.limit("2/second")]

            def get(self):
                return request.method.lower()

            def post(self):
                return request.method.lower()

        class Vb(MethodView):
            decorators = [limiter.limit("1/second, 3/minute")]

            def get(self):
                return request.method.lower()

        class Vc(MethodView):
            def get(self):
                return request.method.lower()

        class Vd(MethodView):
            decorators = [limiter.limit("1/minute", methods=['get'])]

            def get(self):
                return request.method.lower()

            def post(self):
                return request.method.lower()

        app.add_url_rule("/a", view_func=Va.as_view("a"))
        app.add_url_rule("/b", view_func=Vb.as_view("b"))
        app.add_url_rule("/c", view_func=Vc.as_view("c"))
        app.add_url_rule("/d", view_func=Vd.as_view("d"))

        with hiro.Timeline().freeze() as timeline:
            with app.test_client() as cli:
                assert 200 == cli.get("/a").status_code
                assert 200 == cli.get("/a").status_code
                assert 429 == cli.get("/a").status_code
                assert 429 == cli.post("/a").status_code
                assert 200 == cli.get("/b").status_code
                timeline.forward(1)
                assert 200 == cli.get("/b").status_code
                timeline.forward(1)
                assert 200 == cli.get("/b").status_code
                timeline.forward(1)
                assert 429 == cli.get("/b").status_code
                assert 200 == cli.get("/c").status_code
                assert 429 == cli.get("/c").status_code
                assert 200 == cli.get("/d").status_code
                assert 429 == cli.get("/d").status_code
                assert 200 == cli.post("/d").status_code
                assert 429 == cli.post("/d").status_code
                timeline.forward(3600)
                assert 200 == cli.post("/d").status_code

    def test_flask_restful_resource(self):
        app, limiter = self.build_app(default_limits=["1/hour"])
        api = RestfulApi(app)

        class Va(Resource):
            decorators = [limiter.limit("2/second")]

            def get(self):
                return request.method.lower()

            def post(self):
                return request.method.lower()

        class Vb(Resource):
            decorators = [limiter.limit("1/second, 3/minute")]

            def get(self):
                return request.method.lower()

        class Vc(Resource):
            def get(self):
                return request.method.lower()

        class Vd(Resource):
            decorators = [
                limiter.limit("2/second", methods=['GET']),
                limiter.limit("1/second", methods=['POST']),

            ]

            def get(self):
                return request.method.lower()

            def post(self):
                return request.method.lower()

        api.add_resource(Va, "/a")
        api.add_resource(Vb, "/b")
        api.add_resource(Vc, "/c")
        api.add_resource(Vd, "/d")

        with hiro.Timeline().freeze() as timeline:
            with app.test_client() as cli:
                assert 200 == cli.get("/a").status_code
                assert 200 == cli.get("/a").status_code
                assert 429 == cli.get("/a").status_code
                assert 429 == cli.post("/a").status_code
                assert 200 == cli.get("/b").status_code
                assert 200 == cli.get("/d").status_code
                assert 200 == cli.get("/d").status_code
                assert 429 == cli.get("/d").status_code
                assert 200 == cli.post("/d").status_code
                assert 429 == cli.post("/d").status_code
                timeline.forward(1)
                assert 200 == cli.get("/b").status_code
                timeline.forward(1)
                assert 200 == cli.get("/b").status_code
                timeline.forward(1)
                assert 429 == cli.get("/b").status_code
                assert 200 == cli.get("/c").status_code
                assert 429 == cli.get("/c").status_code


class FlaskExtTests(FlaskLimiterTestCase):
    def test_reset(self):
        app, limiter = self.build_app({C.GLOBAL_LIMITS: "1 per day"})

        @app.route("/")
        def null():
            return "Hello Reset"

        with app.test_client() as cli:
            cli.get("/")
            assert "1 per 1 day" in cli.get("/").data.decode()
            limiter.reset()
            assert "Hello Reset" == cli.get("/").data.decode()
            assert "1 per 1 day" in cli.get("/").data.decode()

    def test_reset_unsupported(self):
        app, limiter = self.build_app({
            C.GLOBAL_LIMITS: "1 per day",
            C.STORAGE_URL: 'memcached://localhost:31211'
        })

        @app.route("/")
        def null():
            return "Hello Reset"

        with app.test_client() as cli:
            cli.get("/")
            assert "1 per 1 day" in cli.get("/").data.decode()
            # no op with memcached but no error raised
            limiter.reset()
            assert "1 per 1 day" in cli.get("/").data.decode()

    def test_combined_rate_limits(self):
        app, limiter = self.build_app({
            C.GLOBAL_LIMITS: "1 per hour; 10 per day"
        })

        @app.route("/t1")
        @limiter.limit("100 per hour;10/minute")
        def t1():
            return "t1"

        @app.route("/t2")
        def t2():
            return "t2"

        with hiro.Timeline().freeze():
            with app.test_client() as cli:
                assert 200 == cli.get("/t1").status_code
                assert 200 == cli.get("/t2").status_code
                assert 429 == cli.get("/t2").status_code

    def test_defaults_per_method(self):
        app, limiter = self.build_app({
            C.DEFAULT_LIMITS: "1 per hour",
            C.DEFAULT_LIMITS_PER_METHOD: True
        })

        @app.route("/t1", methods=['GET', 'POST'])
        def t1():
            return "t1"

        with hiro.Timeline().freeze():
            with app.test_client() as cli:
                assert 200 == cli.get("/t1").status_code
                assert 429 == cli.get("/t1").status_code
                assert 200 == cli.post("/t1").status_code
                assert 429 == cli.post("/t1").status_code

    def test_default_limit_with_exemption(self):
        def is_backdoor():
            return request.headers.get('backdoor') == 'true'

        app, limiter = self.build_app({
            C.DEFAULT_LIMITS: "1 per hour",
            C.DEFAULT_LIMITS_EXEMPT_WHEN: is_backdoor
        })

        @app.route("/t1")
        def t1():
            return "test"

        with hiro.Timeline() as timeline:
            with app.test_client() as cli:
                assert cli.get(
                    "/t1", headers={'backdoor': 'true'}
                ).status_code == 200
                assert cli.get(
                    "/t1", headers={'backdoor': 'true'}
                ).status_code == 200
                assert cli.get("/t1").status_code == 200
                assert cli.get("/t1").status_code == 429
                timeline.forward(3600)
                assert cli.get("/t1").status_code == 200

    def test_default_limit_with_conditional_deduction(self):
        def failed_request(response):
            return response.status_code != 200

        app, limiter = self.build_app({
            C.DEFAULT_LIMITS: "1 per hour",
            C.DEFAULT_LIMITS_DEDUCT_WHEN: failed_request
        })

        @app.route("/t1/<path:path>")
        def t1(path):
            if path != "1":
                raise BadRequest()
            return path

        with hiro.Timeline() as timeline:
            with app.test_client() as cli:
                assert cli.get("/t1/1").status_code == 200
                assert cli.get("/t1/1").status_code == 200
                assert cli.get("/t1/2").status_code == 400
                assert cli.get("/t1/1").status_code == 429
                assert cli.get("/t1/2").status_code == 429
                timeline.forward(3600)
                assert cli.get("/t1/1").status_code == 200
                assert cli.get("/t1/2").status_code == 400

    def test_key_func(self):
        app, limiter = self.build_app()

        @app.route("/t1")
        @limiter.limit("100 per minute", lambda: "test")
        def t1():
            return "test"

        with hiro.Timeline().freeze():
            with app.test_client() as cli:
                for i in range(0, 100):
                    assert 200 == \
                        cli.get(
                            "/t1", headers={
                                "X_FORWARDED_FOR": "127.0.0.2"
                            }
                        ).status_code
                assert 429 == cli.get("/t1").status_code

    def test_logging(self, caplog):
        app = Flask(__name__)
        limiter = Limiter(app, key_func=get_remote_address)

        @app.route("/t1")
        @limiter.limit("1/minute")
        def t1():
            return "test"

        with app.test_client() as cli:
            assert 200 == cli.get("/t1").status_code
            assert 429 == cli.get("/t1").status_code
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == 'WARNING'

    def test_reuse_logging(self):
        app = Flask(__name__)
        app_handler = mock.Mock()
        app_handler.level = logging.INFO
        app.logger.addHandler(app_handler)
        limiter = Limiter(app, key_func=get_remote_address)
        for handler in app.logger.handlers:
            limiter.logger.addHandler(handler)

        @app.route("/t1")
        @limiter.limit("1/minute")
        def t1():
            return "42"

        with app.test_client() as cli:
            cli.get("/t1")
            cli.get("/t1")

        assert app_handler.handle.call_count == 1

    def test_disabled_flag(self):
        app, limiter = self.build_app(
            config={C.ENABLED: False}, default_limits=["1/minute"]
        )

        @app.route("/t1")
        def t1():
            return "test"

        @app.route("/t2")
        @limiter.limit("10 per minute")
        def t2():
            return "test"

        with app.test_client() as cli:
            assert cli.get("/t1").status_code == 200
            assert cli.get("/t1").status_code == 200
            for i in range(0, 10):
                assert cli.get("/t2").status_code == 200
            assert cli.get("/t2").status_code == 200

    def test_multiple_apps(self):
        app1 = Flask(__name__)
        app2 = Flask(__name__)

        limiter = Limiter(
            default_limits=["1/second"], key_func=get_remote_address
        )
        limiter.init_app(app1)
        limiter.init_app(app2)

        @app1.route("/ping")
        def ping():
            return "PONG"

        @app1.route("/slowping")
        @limiter.limit("1/minute")
        def slow_ping():
            return "PONG"

        @app2.route("/ping")
        @limiter.limit("2/second")
        def ping_2():
            return "PONG"

        @app2.route("/slowping")
        @limiter.limit("2/minute")
        def slow_ping_2():
            return "PONG"

        with hiro.Timeline().freeze() as timeline:
            with app1.test_client() as cli:
                assert cli.get("/ping").status_code == 200
                assert cli.get("/ping").status_code == 429
                timeline.forward(1)
                assert cli.get("/ping").status_code == 200
                assert cli.get("/slowping").status_code == 200
                timeline.forward(59)
                assert cli.get("/slowping").status_code == 429
                timeline.forward(1)
                assert cli.get("/slowping").status_code == 200
            with app2.test_client() as cli:
                assert cli.get("/ping").status_code == 200
                assert cli.get("/ping").status_code == 200
                assert cli.get("/ping").status_code == 429
                timeline.forward(1)
                assert cli.get("/ping").status_code == 200
                assert cli.get("/slowping").status_code == 200
                timeline.forward(59)
                assert cli.get("/slowping").status_code == 200
                assert cli.get("/slowping").status_code == 429
                timeline.forward(1)
                assert cli.get("/slowping").status_code == 200

    def test_headers_no_breach(self):
        app = Flask(__name__)
        limiter = Limiter(
            app,
            default_limits=["10/minute"],
            headers_enabled=True,
            key_func=get_remote_address
        )

        @app.route("/t1")
        def t1():
            return "test"

        @app.route("/t2")
        @limiter.limit("2/second; 5 per minute; 10/hour")
        def t2():
            return "test"

        with hiro.Timeline().freeze():
            with app.test_client() as cli:
                resp = cli.get("/t1")
                assert resp.headers.get('X-RateLimit-Limit') == '10'
                assert resp.headers.get('X-RateLimit-Remaining') == '9'
                assert resp.headers.get('X-RateLimit-Reset') == \
                    str(int(time.time() + 61))
                assert resp.headers.get('Retry-After') == str(60)
                resp = cli.get("/t2")
                assert resp.headers.get('X-RateLimit-Limit') == '2'
                assert resp.headers.get('X-RateLimit-Remaining') == '1'
                assert resp.headers.get('X-RateLimit-Reset') == \
                    str(int(time.time() + 2))

                assert resp.headers.get('Retry-After') == str(1)

    def test_headers_breach(self):
        app = Flask(__name__)
        limiter = Limiter(
            app,
            default_limits=["10/minute"],
            headers_enabled=True,
            key_func=get_remote_address
        )

        @app.route("/t1")
        @limiter.limit("2/second; 10 per minute; 20/hour")
        def t():
            return "test"

        with hiro.Timeline().freeze() as timeline:
            with app.test_client() as cli:
                for i in range(11):
                    resp = cli.get("/t1")
                    timeline.forward(1)

                assert resp.headers.get('X-RateLimit-Limit') == '10'
                assert resp.headers.get('X-RateLimit-Remaining') == '0'
                assert resp.headers.get('X-RateLimit-Reset') == \
                    str(int(time.time() + 50))
                assert resp.headers.get('Retry-After') == str(int(50))

    def test_retry_after(self):
        app = Flask(__name__)
        _ = Limiter(
            app,
            default_limits=["1/minute"],
            headers_enabled=True,
            key_func=get_remote_address
        )

        @app.route("/t1")
        def t():
            return "test"

        with hiro.Timeline().freeze() as timeline:
            with app.test_client() as cli:
                resp = cli.get("/t1")
                retry_after = int(resp.headers.get('Retry-After'))
                assert retry_after > 0
                timeline.forward(retry_after)
                resp = cli.get("/t1")
                assert resp.status_code == 200

    def test_retry_after_exists_seconds(self):
        app = Flask(__name__)
        _ = Limiter(
            app,
            default_limits=["1/minute"],
            headers_enabled=True,
            key_func=get_remote_address
        )

        @app.route("/t1")
        def t():
            return "", 200, {'Retry-After': '1000000'}

        with app.test_client() as cli:
            resp = cli.get("/t1")

            retry_after = int(resp.headers.get('Retry-After'))
            assert retry_after > 1000

    def test_retry_after_exists_rfc1123(self):
        app = Flask(__name__)
        _ = Limiter(
            app,
            default_limits=["1/minute"],
            headers_enabled=True,
            key_func=get_remote_address
        )

        @app.route("/t1")
        def t():
            return "", 200, {'Retry-After': 'Sun, 06 Nov 2032 01:01:01 GMT'}

        with app.test_client() as cli:
            resp = cli.get("/t1")

            retry_after = int(resp.headers.get('Retry-After'))
            assert retry_after > 1000

    def test_custom_headers_from_setter(self):
        app = Flask(__name__)
        limiter = Limiter(
            app,
            default_limits=["10/minute"],
            headers_enabled=True,
            key_func=get_remote_address,
            retry_after='http-date'
        )
        limiter._header_mapping[HEADERS.RESET] = 'X-Reset'
        limiter._header_mapping[HEADERS.LIMIT] = 'X-Limit'
        limiter._header_mapping[HEADERS.REMAINING] = 'X-Remaining'

        @app.route("/t1")
        @limiter.limit("2/second; 10 per minute; 20/hour")
        def t():
            return "test"

        with hiro.Timeline().freeze(0) as timeline:
            with app.test_client() as cli:
                for i in range(11):
                    resp = cli.get("/t1")
                    timeline.forward(1)

                assert resp.headers.get('X-Limit') == '10'
                assert resp.headers.get('X-Remaining') == '0'
                assert resp.headers.get(
                    'X-Reset'
                ) == str(int(time.time() + 50))
                assert resp.headers.get(
                    'Retry-After'
                ) == 'Thu, 01 Jan 1970 00:01:01 GMT'

    def test_custom_headers_from_config(self):
        app = Flask(__name__)
        app.config.setdefault(C.HEADER_LIMIT, "X-Limit")
        app.config.setdefault(C.HEADER_REMAINING, "X-Remaining")
        app.config.setdefault(C.HEADER_RESET, "X-Reset")
        limiter = Limiter(
            app,
            default_limits=["10/minute"],
            headers_enabled=True,
            key_func=get_remote_address
        )

        @app.route("/t1")
        @limiter.limit("2/second; 10 per minute; 20/hour")
        def t():
            return "test"

        with hiro.Timeline().freeze() as timeline:
            with app.test_client() as cli:
                for i in range(11):
                    resp = cli.get("/t1")
                    timeline.forward(1)

                assert resp.headers.get('X-Limit') == '10'
                assert resp.headers.get('X-Remaining') == '0'
                assert resp.headers.get(
                    'X-Reset'
                ) == str(int(time.time() + 50))

    def test_custom_headers_from_setter_and_config(self):
        app = Flask(__name__)
        app.config.setdefault(C.HEADER_LIMIT, "Limit")
        app.config.setdefault(C.HEADER_REMAINING, "Remaining")
        app.config.setdefault(C.HEADER_RESET, "Reset")
        limiter = Limiter(
            default_limits=["10/minute"],
            headers_enabled=True,
            key_func=get_remote_address
        )
        limiter._header_mapping[HEADERS.REMAINING] = 'Available'
        limiter.init_app(app)

        @app.route("/t1")
        def t():
            return "test"

        with app.test_client() as cli:
            for i in range(11):
                resp = cli.get("/t1")

            assert resp.headers.get('Limit') == '10'
            assert resp.headers.get('Available') == '0'
            assert resp.headers.get('Reset') is not None

    def test_application_shared_limit(self):
        app, limiter = self.build_app(application_limits=["2/minute"])

        @app.route("/t1")
        def t1():
            return "route1"

        @app.route("/t2")
        def t2():
            return "route2"

        with hiro.Timeline().freeze():
            with app.test_client() as cli:
                assert 200 == cli.get("/t1").status_code
                assert 200 == cli.get("/t2").status_code
                assert 429 == cli.get("/t1").status_code

    def test_callable_default_limit(self):
        app, limiter = self.build_app(default_limits=[lambda: "1/minute"])

        @app.route("/t1")
        def t1():
            return "t1"

        @app.route("/t2")
        def t2():
            return "t2"

        with hiro.Timeline().freeze():
            with app.test_client() as cli:
                assert cli.get("/t1").status_code == 200
                assert cli.get("/t2").status_code == 200
                assert cli.get("/t1").status_code == 429
                assert cli.get("/t2").status_code == 429

    def test_callable_application_limit(self):

        app, limiter = self.build_app(application_limits=[lambda: "1/minute"])

        @app.route("/t1")
        def t1():
            return "t1"

        @app.route("/t2")
        def t2():
            return "t2"

        with hiro.Timeline().freeze():
            with app.test_client() as cli:
                assert cli.get("/t1").status_code == 200
                assert cli.get("/t2").status_code == 429

    def test_no_auto_check(self):
        app, limiter = self.build_app(auto_check=False)

        @limiter.limit("1/second", per_method=True)
        @app.route("/", methods=["GET", "POST"])
        def root():
            return "root"

        with hiro.Timeline().freeze():
            with app.test_client() as cli:
                assert 200 == cli.get("/").status_code
                assert 200 == cli.get("/").status_code

        # attach before_request to perform check
        @app.before_request
        def _():
            limiter.check()

        with hiro.Timeline().freeze():
            with app.test_client() as cli:
                assert 200 == cli.get("/").status_code
                assert 429 == cli.get("/").status_code

    def test_custom_key_prefix(self):
        app1, limiter1 = self.build_app(
            key_prefix="moo", storage_uri="redis://localhost:36379"
        )
        app2, limiter2 = self.build_app(
            {C.KEY_PREFIX: "cow"},
            storage_uri="redis://localhost:36379"
        )
        app3, limiter3 = self.build_app(storage_uri="redis://localhost:36379")

        @app1.route("/test")
        @limiter1.limit("1/day")
        def app1_test():
            return "app1 test"

        @app2.route("/test")
        @limiter2.limit("1/day")
        def app2_test():
            return "app1 test"

        @app3.route("/test")
        @limiter3.limit("1/day")
        def app3_test():
            return "app1 test"

        with app1.test_client() as cli:
            resp = cli.get("/test")
            assert 200 == resp.status_code
            resp = cli.get("/test")
            assert 429 == resp.status_code
        with app2.test_client() as cli:
            resp = cli.get("/test")
            assert 200 == resp.status_code
            resp = cli.get("/test")
            assert 429 == resp.status_code
        with app3.test_client() as cli:
            resp = cli.get("/test")
            assert 200 == resp.status_code
            resp = cli.get("/test")
            assert 429 == resp.status_code
