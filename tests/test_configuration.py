import math
import time

import pytest
from flask import Flask
from limits.errors import ConfigurationError
from limits.storage import MemcachedStorage
from limits.strategies import MovingWindowRateLimiter

from flask_limiter.extension import HEADERS, C, Limiter
from flask_limiter.util import get_remote_address


def test_invalid_strategy():
    app = Flask(__name__)
    app.config.setdefault(C.STRATEGY, "fubar")
    with pytest.raises(ConfigurationError):
        Limiter(app, key_func=get_remote_address)


def test_invalid_storage_string():
    app = Flask(__name__)
    app.config.setdefault(C.STORAGE_URI, "fubar://localhost:1234")
    with pytest.raises(ConfigurationError):
        Limiter(app, key_func=get_remote_address)


def test_constructor_arguments_over_config(redis_connection):
    app = Flask(__name__)
    app.config.setdefault(C.STRATEGY, "fixed-window-elastic-expiry")
    limiter = Limiter(strategy="moving-window", key_func=get_remote_address)
    limiter.init_app(app)
    app.config.setdefault(C.STORAGE_URI, "redis://localhost:46379")
    assert type(limiter._limiter) == MovingWindowRateLimiter
    limiter = Limiter(
        storage_uri="memcached://localhost:31211", key_func=get_remote_address
    )
    limiter.init_app(app)
    assert type(limiter._storage) == MemcachedStorage


def test_header_names_config():
    app = Flask(__name__)
    app.config.setdefault(C.HEADER_LIMIT, "XX-Limit")
    app.config.setdefault(C.HEADER_REMAINING, "XX-Remaining")
    app.config.setdefault(C.HEADER_RESET, "XX-Reset")
    limiter = Limiter(
        key_func=get_remote_address, headers_enabled=True, default_limits=["1/second"]
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
        key_func=get_remote_address,
        headers_enabled=True,
        default_limits=["1/second"],
        header_name_mapping={
            HEADERS.LIMIT: "XX-Limit",
            HEADERS.REMAINING: "XX-Remaining",
            HEADERS.RESET: "XX-Reset",
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
    app.config.setdefault(C.ENABLED, False)
    app.config.setdefault(C.STORAGE_URI, "fubar://")

    limiter = Limiter(app, key_func=get_remote_address, default_limits=["1/hour"])

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
    limiter = Limiter(key_func=get_remote_address, default_limits=["1/hour"])

    @app.route("/")
    @limiter.limit("2/hour")
    def root():
        return "root"

    with app.test_client() as client:
        assert client.get("/").status_code == 200
        assert client.get("/").status_code == 200
        assert client.get("/").status_code == 200
