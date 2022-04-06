import socket

import pymemcache
import pymongo
import pytest
import redis
from flask import Flask

from flask_limiter import Limiter
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
        limiter_args.setdefault("key_func", get_remote_address)
        limiter = Limiter(app, **limiter_args)

        return app, limiter

    return _build_app_and_extension


@pytest.fixture(scope="session")
def docker_compose_files(pytestconfig):
    return ["docker-compose.yml"]
