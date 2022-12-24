import hiro

from flask_limiter import RateLimitExceeded


def test_static_limit(extension_factory):
    app, limiter = extension_factory()

    @app.route("/t1")
    def t1():
        with limiter.limit("1/second"):
            resp = "ok"
        try:
            with limiter.limit("1/day"):
                resp += "maybe"
        except RateLimitExceeded:
            pass
        finally:
            return resp

    with hiro.Timeline().freeze() as timeline:
        with app.test_client() as cli:
            response = cli.get("/t1")
            assert 200 == response.status_code
            assert "okmaybe" == response.text
            assert 429 == cli.get("/t1").status_code
            timeline.forward(1)
            response = cli.get("/t1")
            assert 200 == response.status_code
            assert "ok" == response.text


def test_dynamic_limits(extension_factory):
    app, limiter = extension_factory()

    @app.route("/t1")
    def t1():
        with limiter.limit(lambda: "1/second"):
            return "test"

    with hiro.Timeline().freeze():
        with app.test_client() as cli:
            assert 200 == cli.get("/t1").status_code
            assert 429 == cli.get("/t1").status_code
