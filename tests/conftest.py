import socket

import pymemcache
import pymongo
import pytest
import redis
from flask import Blueprint, Flask, request
from flask.views import View

from flask_limiter import ExemptionScope, Limiter
from flask_limiter.util import get_remote_address


def ping_socket(host, port):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect((host, port))

        return True
    except Exception:
        return False


@pytest.fixture
def redis_connection(docker_services):
    docker_services.start("redis")
    docker_services.wait_for_service("redis", 6379, ping_socket)
    r = redis.from_url("redis://localhost:46379")
    r.flushall()

    return r


@pytest.fixture
def memcached_connection(docker_services):
    docker_services.start("memcached")
    docker_services.wait_for_service("memcached", 11211, ping_socket)
    return pymemcache.Client(("localhost", 31211))


@pytest.fixture
def mongo_connection(docker_services):
    docker_services.start("mongodb")
    docker_services.wait_for_service("mongodb", 27017, ping_socket)
    return pymongo.MongoClient("mongodb://localhost:47017")


@pytest.fixture
def extension_factory():
    def _build_app_and_extension(config={}, **limiter_args):
        app = Flask(__name__)

        for k, v in config.items():
            app.config.setdefault(k, v)
        key_func = limiter_args.pop("key_func", get_remote_address)
        limiter = Limiter(key_func, app=app, **limiter_args)

        return app, limiter

    return _build_app_and_extension


@pytest.fixture
def kitchensink_factory(extension_factory):
    def _(**kwargs):
        def dynamic_default():
            if request.headers.get("X-Evil"):
                return "10/minute"
            return "20/minute"

        def dynamic_default_cost():
            if request.headers.get("X-Evil"):
                return 2
            return 1

        app, limiter = extension_factory(
            default_limits=["10/second", "1000/hour", dynamic_default],
            default_limits_exempt_when=lambda: request.headers.get("X-Internal"),
            default_limits_deduct_when=lambda response: response.status_code != 200,
            default_limits_cost=dynamic_default_cost,
            application_limits=["5000/hour"],
            headers_enabled=True,
            **kwargs
        )

        @app.route("/")
        def root():
            return "42"

        health_blueprint = Blueprint("health", __name__, url_prefix="/health")

        @health_blueprint.route("/")
        def health():
            return "ok"

        app.register_blueprint(health_blueprint)

        class ResourceView(View):
            methods = ["GET", "POST"]
            decorators = [limiter.limit("5/second", per_method=True)]

            def dispatch_request(self):
                return request.method.lower()

        app.add_url_rule("/resource", view_func=ResourceView.as_view("resource"))

        limiter.exempt(
            health_blueprint,
            flags=ExemptionScope.DEFAULT
            | ExemptionScope.APPLICATION
            | ExemptionScope.ANCESTORS,
        )

        return app, limiter

    return _


@pytest.fixture(scope="session")
def docker_services_project_name():
    return "flask-limiter"


@pytest.fixture(scope="session")
def docker_compose_files(pytestconfig):
    return ["docker-compose.yml"]
