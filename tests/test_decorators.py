import functools
from functools import wraps

import hiro
import mock
from flask import Blueprint, request, current_app, Flask, g
from werkzeug.exceptions import BadRequest

from flask_limiter import Limiter
from flask_limiter.util import get_ipaddr, get_remote_address


def test_multiple_decorators(extension_factory):
    app, limiter = extension_factory(key_func=get_ipaddr)

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


def test_exempt_routes(extension_factory):
    app, limiter = extension_factory(default_limits=["1/minute"])

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


def test_decorated_limit_with_conditional_deduction(extension_factory):
    app, limiter = extension_factory()

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


def test_shared_limit_with_conditional_deduction(extension_factory):
    app, limiter = extension_factory()

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


def test_header_ordering_with_conditional_deductions(extension_factory):
    app, limiter = extension_factory(
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
            assert resp.headers.get('X-RateLimit-Limit') == '2'
            assert resp.headers.get('X-RateLimit-Remaining') == '2'
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


def test_decorated_limits_with_combined_defaults(extension_factory):
    app, limiter = extension_factory(
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


def test_decorated_limit_with_combined_defaults_per_method(extension_factory):
    app, limiter = extension_factory(
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


def test_decorated_dynamic_limits(extension_factory):
    app, limiter = extension_factory(
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


def test_invalid_decorated_dynamic_limits(caplog):
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


def test_invalid_decorated_static_limits(caplog):
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


def test_named_shared_limit(extension_factory):
    app, limiter = extension_factory()
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


def test_dynamic_shared_limit(extension_factory):
    app, limiter = extension_factory()
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


def test_conditional_limits():
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


def test_conditional_shared_limits():
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


def test_whitelisting():

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


def test_separate_method_limits(extension_factory):
    app, limiter = extension_factory()

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


def test_explicit_method_limits(extension_factory):
    app, limiter = extension_factory(default_limits=['2/second'])

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


def test_decorated_limit_immediate(extension_factory):
    app, limiter = extension_factory(default_limits=["1/minute"])

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


def test_decorated_shared_limit_immediate(extension_factory):

    app, limiter = extension_factory(default_limits=['1/minute'])
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


def test_backward_compatibility_with_incorrect_ordering(extension_factory):
    app, limiter = extension_factory()

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
