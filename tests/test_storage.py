import hiro
import pytest


@pytest.fixture(autouse=True)
def setup(redis_connection, memcached_connection, mongo_connection):
    redis_connection.flushall()
    memcached_connection.flush_all()


@pytest.mark.parametrize(
    "storage_uri",
    [
        "memcached://localhost:31211",
        "redis://localhost:46379",
        "mongodb://localhost:47017",
    ],
)
def test_fixed_window(extension_factory, storage_uri):
    app, limiter = extension_factory(
        application_limits=["2/minute"],
        storage_uri=storage_uri,
        strategy="fixed-window",
    )

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


@pytest.mark.parametrize(
    "storage_uri",
    [
        "redis://localhost:46379",
        "mongodb://localhost:47017",
    ],
)
def test_moving_window(extension_factory, storage_uri):
    app, limiter = extension_factory(
        application_limits=["2/minute"],
        storage_uri=storage_uri,
        strategy="moving-window",
    )

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
