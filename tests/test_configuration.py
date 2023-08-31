import math
import time

import hiro
import pytest
from flask import Flask
from limits.errors import ConfigurationError
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter

from flask_limiter import HeaderNames
from flask_limiter.constants import ConfigVars
from flask_limiter.extension import Limiter
from flask_limiter.util import get_remote_address


def test_invalid_strategy():
    app = Flask(__name__)
    app.config.setdefault(ConfigVars.STRATEGY, "fubar")
    with pytest.raises(ConfigurationError):
        Limiter(get_remote_address, app=app)


def test_invalid_storage_string():
    app = Flask(__name__)
    app.config.setdefault(ConfigVars.STORAGE_URI, "fubar://localhost:1234")
    with pytest.raises(ConfigurationError):
        Limiter(get_remote_address, app=app)


def test_constructor_arguments_over_config(redis_connection):
    app = Flask(__name__)
    app.config.setdefault(ConfigVars.STRATEGY, "fixed-window-elastic-expiry")
    limiter = Limiter(get_remote_address, strategy="moving-window")
    limiter.init_app(app)
    app.config.setdefault(ConfigVars.STORAGE_URI, "redis://localhost:46379")
    app.config.setdefault(ConfigVars.APPLICATION_LIMITS, "1/minute")
    app.config.setdefault(ConfigVars.META_LIMITS, "1/hour")
    assert type(limiter._limiter) == MovingWindowRateLimiter
    limiter = Limiter(get_remote_address, storage_uri="memory://")
    limiter.init_app(app)
    assert type(limiter._storage) == MemoryStorage

    @app.route("/")
    def root():
        return "root"

    with hiro.Timeline().freeze() as timeline:
        with app.test_client() as cli:
            assert cli.get("/").status_code == 200
            assert cli.get("/").status_code == 429
            timeline.forward(60)
            assert cli.get("/").status_code == 429


def test_header_names_config():
    app = Flask(__name__)
    app.config.setdefault(ConfigVars.HEADER_LIMIT, "XX-Limit")
    app.config.setdefault(ConfigVars.HEADER_REMAINING, "XX-Remaining")
    app.config.setdefault(ConfigVars.HEADER_RESET, "XX-Reset")
    limiter = Limiter(
        get_remote_address, headers_enabled=True, default_limits=["1/second"]
    )
    limiter.init_app(app)

    @app.route("/")
    def root():
        return "42"

    with app.test_client() as client:
        resp = client.get("/")
        assert resp.headers["XX-Limit"] == "1"
        assert resp.headers["XX-Remaining"] == "0"
        assert resp.headers["XX-Reset"] == str(math.ceil(time.time() + 1))


def test_header_names_constructor():
    app = Flask(__name__)
    limiter = Limiter(
        get_remote_address,
        headers_enabled=True,
        default_limits=["1/second"],
        header_name_mapping={
            HeaderNames.LIMIT: "XX-Limit",
            HeaderNames.REMAINING: "XX-Remaining",
            HeaderNames.RESET: "XX-Reset",
        },
    )
    limiter.init_app(app)

    @app.route("/")
    def root():
        return "42"

    with app.test_client() as client:
        resp = client.get("/")
        assert resp.headers["XX-Limit"] == "1"
        assert resp.headers["XX-Remaining"] == "0"
        assert resp.headers["XX-Reset"] == str(math.ceil(time.time() + 1))


def test_invalid_config_with_disabled():
    app = Flask(__name__)
    app.config.setdefault(ConfigVars.ENABLED, False)
    app.config.setdefault(ConfigVars.STORAGE_URI, "fubar://")

    limiter = Limiter(get_remote_address, app=app, default_limits=["1/hour"])

    @app.route("/")
    def root():
        return "root"

    @app.route("/explicit")
    @limiter.limit("2/hour")
    def explicit():
        return "explicit"

    with app.test_client() as client:
        assert client.get("/").status_code == 200
        assert client.get("/").status_code == 200
        assert client.get("/explicit").status_code == 200
        assert client.get("/explicit").status_code == 200
        assert client.get("/explicit").status_code == 200


def test_uninitialized_limiter():
    app = Flask(__name__)
    limiter = Limiter(get_remote_address, default_limits=["1/hour"])

    @app.route("/")
    @limiter.limit("2/hour")
    def root():
        return "root"

    with app.test_client() as client:
        assert client.get("/").status_code == 200
        assert client.get("/").status_code == 200
        assert client.get("/").status_code == 200
