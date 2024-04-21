import json
from unittest.mock import patch

import hiro
from flask import make_response

from flask_limiter.constants import ConfigVars


def test_error_message(extension_factory):
    app, limiter = extension_factory({ConfigVars.DEFAULT_LIMITS: "1 per day"})

    @app.route("/")
    def null():
        return ""

    with app.test_client() as cli:

        @app.errorhandler(429)
        def ratelimit_handler(e):
            return make_response(
                '{"error" : "rate limit %s"}' % str(e.description), 429
            )

        cli.get("/")
        assert "1 per 1 day" in cli.get("/").data.decode()

        assert {"error": "rate limit 1 per 1 day"} == json.loads(
            cli.get("/").data.decode()
        )


def test_custom_error_message(extension_factory):
    app, limiter = extension_factory()

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

    s1 = limiter.shared_limit("1/second", scope="error_message", error_message="tres")

    @app.route("/t3")
    @s1
    def t3():
        return "3"

    with hiro.Timeline().freeze():
        with app.test_client() as cli:
            cli.get("/t1")
            resp = cli.get("/t1")
            assert 429 == resp.status_code
            assert resp.data == b"uno"
            cli.get("/t2")
            resp = cli.get("/t2")
            assert 429 == resp.status_code
            assert resp.data == b"dos"
            cli.get("/t3")
            resp = cli.get("/t3")
            assert 429 == resp.status_code
            assert resp.data == b"tres"


def test_swallow_error(extension_factory):
    app, limiter = extension_factory(
        {
            ConfigVars.DEFAULT_LIMITS: "1 per day",
            ConfigVars.HEADERS_ENABLED: True,
            ConfigVars.SWALLOW_ERRORS: True,
        }
    )

    @app.route("/")
    def null():
        return "ok"

    with app.test_client() as cli:
        with patch("limits.strategies.FixedWindowRateLimiter.hit") as hit:

            def raiser(*a, **k):
                raise Exception

            hit.side_effect = raiser
            assert "ok" in cli.get("/").data.decode()
        with patch(
            "limits.strategies.FixedWindowRateLimiter.get_window_stats"
        ) as get_window_stats:

            def raiser(*a, **k):
                raise Exception

            get_window_stats.side_effect = raiser
            assert "ok" in cli.get("/").data.decode()


def test_swallow_error_conditional_deduction(extension_factory):
    def conditional_deduct(_):
        return True

    app, limiter = extension_factory(
        {
            ConfigVars.DEFAULT_LIMITS: "1 per day",
            ConfigVars.SWALLOW_ERRORS: True,
            ConfigVars.DEFAULT_LIMITS_DEDUCT_WHEN: conditional_deduct,
        }
    )

    @app.route("/")
    def null():
        return "ok"

    with app.test_client() as cli:
        with patch("limits.strategies.FixedWindowRateLimiter.hit") as hit:

            def raiser(*a, **k):
                raise Exception

            hit.side_effect = raiser
            assert "ok" in cli.get("/").data.decode()


def test_no_swallow_error(extension_factory):
    app, limiter = extension_factory(
        {ConfigVars.DEFAULT_LIMITS: "1 per day", ConfigVars.HEADERS_ENABLED: True}
    )

    @app.route("/")
    def null():
        return "ok"

    @app.errorhandler(500)
    def e500(e):
        return str(e.original_exception), 500

    def raiser(*a, **k):
        raise Exception("underlying")

    with app.test_client() as cli:
        with patch("limits.strategies.FixedWindowRateLimiter.hit") as hit:
            hit.side_effect = raiser
            assert 500 == cli.get("/").status_code
            assert "underlying" == cli.get("/").data.decode()
        with patch(
            "limits.strategies.FixedWindowRateLimiter.get_window_stats"
        ) as get_window_stats:
            get_window_stats.side_effect = raiser
            assert 500 == cli.get("/").status_code
            assert "underlying" == cli.get("/").data.decode()


def test_no_swallow_error_conditional_deduction(extension_factory):
    def conditional_deduct(_):
        return True

    app, limiter = extension_factory(
        {
            ConfigVars.DEFAULT_LIMITS: "1 per day",
            ConfigVars.SWALLOW_ERRORS: False,
            ConfigVars.DEFAULT_LIMITS_DEDUCT_WHEN: conditional_deduct,
        }
    )

    @app.route("/")
    def null():
        return "ok"

    with app.test_client() as cli:
        with patch("limits.strategies.FixedWindowRateLimiter.hit") as hit:

            def raiser(*a, **k):
                raise Exception

            hit.side_effect = raiser
            assert 500 == cli.get("/").status_code


def test_fallback_to_memory_config(redis_connection, extension_factory):
    _, limiter = extension_factory(
        config={ConfigVars.ENABLED: True},
        default_limits=["5/minute"],
        storage_uri="redis://localhost:46379",
        in_memory_fallback=["1/minute"],
    )
    assert len(limiter._in_memory_fallback) == 1
    assert limiter._in_memory_fallback_enabled

    _, limiter = extension_factory(
        config={ConfigVars.ENABLED: True, ConfigVars.IN_MEMORY_FALLBACK: "1/minute"},
        default_limits=["5/minute"],
        storage_uri="redis://localhost:46379",
    )
    assert len(limiter._in_memory_fallback) == 1
    assert limiter._in_memory_fallback_enabled

    _, limiter = extension_factory(
        config={ConfigVars.ENABLED: True, ConfigVars.IN_MEMORY_FALLBACK_ENABLED: True},
        default_limits=["5/minute"],
        storage_uri="redis://localhost:46379",
    )
    assert limiter._in_memory_fallback_enabled

    _, limiter = extension_factory(
        config={ConfigVars.ENABLED: True},
        default_limits=["5/minute"],
        storage_uri="redis://localhost:46379",
        in_memory_fallback_enabled=True,
    )


def test_fallback_to_memory_backoff_check(redis_connection, extension_factory):
    app, limiter = extension_factory(
        config={ConfigVars.ENABLED: True},
        default_limits=["5/minute"],
        storage_uri="redis://localhost:46379",
        in_memory_fallback=["1/minute"],
    )

    @app.route("/t1")
    def t1():
        return "test"

    with app.test_client() as cli:

        def raiser(*a):
            raise Exception("redis dead")

        with hiro.Timeline() as timeline:
            with patch("redis.Redis.execute_command") as exec_command:
                exec_command.side_effect = raiser
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


def test_fallback_to_memory_with_global_override(redis_connection, extension_factory):
    app, limiter = extension_factory(
        config={ConfigVars.ENABLED: True},
        default_limits=["5/minute"],
        storage_uri="redis://localhost:46379",
        in_memory_fallback=["1/minute"],
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

        with patch("redis.Redis.execute_command") as exec_command:
            exec_command.side_effect = raiser
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


def test_fallback_to_memory(extension_factory):
    app, limiter = extension_factory(
        config={ConfigVars.ENABLED: True},
        default_limits=["2/minute"],
        storage_uri="redis://localhost:46379",
        in_memory_fallback_enabled=True,
        headers_enabled=True,
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

        with patch("redis.Redis.execute_command") as exec_command:
            exec_command.side_effect = raiser
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
