import hiro
from flask import Blueprint, Flask, current_app

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


def test_blueprint(extension_factory):
    app, limiter = extension_factory(default_limits=["1/minute"])
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


def test_register_blueprint(extension_factory):
    app, limiter = extension_factory(default_limits=["1/minute"])
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


def test_invalid_decorated_static_limit_blueprint(caplog):
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


def test_invalid_decorated_dynamic_limits_blueprint(caplog):
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
