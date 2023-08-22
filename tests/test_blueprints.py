import datetime
import logging

import hiro
from flask import Blueprint, Flask, current_app

from flask_limiter import ExemptionScope, Limiter
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


def test_blueprint_static_exempt(extension_factory):
    app, limiter = extension_factory(default_limits=["1/minute"])
    bp = Blueprint("main", __name__, static_folder="static")
    app.register_blueprint(bp, url_prefix="/bp")

    with app.test_client() as cli:
        assert cli.get("/bp/static/image.png").status_code == 200
        assert cli.get("/bp/static/image.png").status_code == 200


def test_blueprint_limit_with_route_limits(extension_factory):
    app, limiter = extension_factory(default_limits=["1/minute"])
    bp = Blueprint("main", __name__)

    @app.route("/")
    def root():
        return "root"

    @bp.route("/t1")
    def t1():
        return "test"

    @bp.route("/t2")
    @limiter.limit("10 per minute")
    def t2():
        return "test"

    @bp.route("/t3")
    @limiter.limit("3 per hour", override_defaults=False)
    def t3():
        return "test"

    limiter.limit("2/minute")(bp)

    app.register_blueprint(bp)

    with hiro.Timeline() as timeline:
        with app.test_client() as cli:
            assert cli.get("/").status_code == 200
            assert cli.get("/").status_code == 429
            assert cli.get("/t1").status_code == 200
            assert cli.get("/t1").status_code == 200
            assert cli.get("/t1").status_code == 429
            for i in range(0, 10):
                assert cli.get("/t2").status_code == 200
            assert cli.get("/t2").status_code == 429

            assert cli.get("/t3").status_code == 200
            assert cli.get("/t3").status_code == 200
            assert cli.get("/t3").status_code == 429
            timeline.forward(datetime.timedelta(minutes=1))
            assert cli.get("/t3").status_code == 200
            timeline.forward(datetime.timedelta(minutes=1))
            assert cli.get("/t3").status_code == 429


def test_nested_blueprint_exemption_explicit(extension_factory):
    app, limiter = extension_factory(default_limits=["1/minute"])
    parent_bp = Blueprint("parent", __name__, url_prefix="/parent")
    child_bp = Blueprint("child", __name__, url_prefix="/child")

    limiter.exempt(parent_bp)
    limiter.exempt(child_bp)

    @app.route("/")
    def root():
        return "42"

    @parent_bp.route("/")
    def parent():
        return "41"

    @child_bp.route("/")
    def child():
        return "40"

    parent_bp.register_blueprint(child_bp)
    app.register_blueprint(parent_bp)

    with app.test_client() as cli:
        assert cli.get("/").status_code == 200
        assert cli.get("/").status_code == 429
        assert cli.get("/parent/").status_code == 200
        assert cli.get("/parent/").status_code == 200
        assert cli.get("/parent/child/").status_code == 200
        assert cli.get("/parent/child/").status_code == 200


def test_nested_blueprint_exemption_legacy(extension_factory):
    """
    To capture legacy behavior, exempting a blueprint
    will not automatically exempt nested blueprints
    """
    app, limiter = extension_factory(default_limits=["1/minute"])
    parent_bp = Blueprint("parent", __name__, url_prefix="/parent")
    child_bp = Blueprint("child", __name__, url_prefix="/child")

    limiter.exempt(parent_bp)

    @app.route("/")
    def root():
        return "42"

    @parent_bp.route("/")
    def parent():
        return "41"

    @child_bp.route("/")
    def child():
        return "40"

    parent_bp.register_blueprint(child_bp)
    app.register_blueprint(parent_bp)

    with app.test_client() as cli:
        assert cli.get("/").status_code == 200
        assert cli.get("/").status_code == 429
        assert cli.get("/parent/").status_code == 200
        assert cli.get("/parent/").status_code == 200
        assert cli.get("/parent/child/").status_code == 200
        assert cli.get("/parent/child/").status_code == 429


def test_nested_blueprint_exemption_nested(extension_factory):
    app, limiter = extension_factory(default_limits=["1/minute"])
    parent_bp = Blueprint("parent", __name__, url_prefix="/parent")
    child_bp = Blueprint("child", __name__, url_prefix="/child")

    limiter.exempt(parent_bp, flags=ExemptionScope.DEFAULT | ExemptionScope.DESCENDENTS)

    @app.route("/")
    def root():
        return "42"

    @parent_bp.route("/")
    def parent():
        return "41"

    @child_bp.route("/")
    def child():
        return "40"

    parent_bp.register_blueprint(child_bp)
    app.register_blueprint(parent_bp)

    with app.test_client() as cli:
        assert cli.get("/").status_code == 200
        assert cli.get("/").status_code == 429
        assert cli.get("/parent/").status_code == 200
        assert cli.get("/parent/").status_code == 200
        assert cli.get("/parent/child/").status_code == 200
        assert cli.get("/parent/child/").status_code == 200


def test_nested_blueprint_exemption_ridiculous(extension_factory):
    app, limiter = extension_factory(
        default_limits=["1/minute"], application_limits=["5/day"]
    )
    n1 = Blueprint("n1", __name__, url_prefix="/n1")
    n2 = Blueprint("n2", __name__, url_prefix="/n2")
    n1_1 = Blueprint("n1_1", __name__, url_prefix="/n1_1")
    n2_1 = Blueprint("n2_1", __name__, url_prefix="/n2_1")
    n1_1_1 = Blueprint("n1_1_1", __name__, url_prefix="/n1_1_1")
    n1_1_2 = Blueprint("n1_1_2", __name__, url_prefix="/n1_1_2")
    n2_1_1 = Blueprint("n2_1_1", __name__, url_prefix="/n2_1_1")

    @app.route("/")
    def root():
        return "42"

    @n1.route("/")
    def _n1():
        return "n1"

    @n1_1.route("/")
    def _n1_1():
        return "n1_1"

    @n1_1_1.route("/")
    def _n1_1_1():
        return "n1_1_1"

    @n1_1_2.route("/")
    def _n1_1_2():
        return "n1_1_2"

    @n2.route("/")
    def _n2():
        return "n2"

    @n2_1.route("/")
    def _n2_1():
        return "n2_1"

    @n2_1_1.route("/")
    def _n2_1_1():
        return "n2_1_1"

    # All routes under n1, and it's descendents are exempt for default/application limits
    limiter.exempt(
        n1,
        flags=ExemptionScope.DEFAULT
        | ExemptionScope.APPLICATION
        | ExemptionScope.DESCENDENTS,
    )
    # n1 descendents are exempt from application & defaults so need their own limits
    limiter.limit("2/minute")(n1_1)
    # n1_1_1 wants to not inherit n1_1's limits and is otherwise exempt from
    # application and defaults due to n1's exemptions.
    limiter.exempt(n1_1_1, flags=ExemptionScope.ANCESTORS)
    # n1_1_2 will not get it's parent (n1_1) limit and sets it's own
    limiter.limit("3/minute")(n1_1_2)

    # n2 overrides the default limits but still gets the application wide limits
    limiter.limit("2/minute")(n2)
    # n2_1 wants out of defaults and application limits
    limiter.exempt(n2_1, flags=ExemptionScope.DEFAULT | ExemptionScope.APPLICATION)
    # but want its own limits
    limiter.limit("3/minute")(n2_1)
    # n2_1_1 want's out of it's parent's limits only but wants to keep application/default limits
    limiter.exempt(n2_1_1, flags=ExemptionScope.ANCESTORS)

    n1.register_blueprint(n1_1)
    n1_1.register_blueprint(n1_1_1)
    n1_1.register_blueprint(n1_1_2)
    n2.register_blueprint(n2_1)
    n2_1.register_blueprint(n2_1_1)
    app.register_blueprint(n1)
    app.register_blueprint(n2)

    with hiro.Timeline() as timeline:
        with app.test_client() as cli:
            assert cli.get("/").status_code == 200
            assert cli.get("/").status_code == 429  # Default hit
            # application: exempt, default: exempt, explicit: none
            assert cli.get("/n1/").status_code == 200
            assert cli.get("/n1/").status_code == 200
            # application: exempt from n1, default exempt from n1 & overridden
            # by explicit: 2/minute
            assert cli.get("/n1/n1_1/").status_code == 200
            assert cli.get("/n1/n1_1/").status_code == 200
            assert cli.get("/n1/n1_1/").status_code == 429
            # application: exempt from n1, default: exempt from n1, inherited: exempt,
            # explicit: none
            assert cli.get("/n1/n1_1/n1_1_1/").status_code == 200
            assert cli.get("/n1/n1_1/n1_1_1/").status_code == 200
            assert cli.get("/n1/n1_1/n1_1_1/").status_code == 200
            # application: exempt from n1, default: exempt from n1, inherited: exempt,
            # explicit: 3/minute
            assert cli.get("/n1/n1_1/n1_1_2/").status_code == 200
            assert cli.get("/n1/n1_1/n1_1_2/").status_code == 200
            assert cli.get("/n1/n1_1/n1_1_2/").status_code == 200
            assert cli.get("/n1/n1_1/n1_1_2/").status_code == 429
            # application: active, default: exempt, explicit: 2/minute
            assert cli.get("/n2/").status_code == 200
            assert cli.get("/n2/").status_code == 200
            assert cli.get("/n2/").status_code == 429
            # application: exempt, default: exempt, explicit: 3/minute therefore overriding n2
            assert cli.get("/n2/n2_1/").status_code == 200
            assert cli.get("/n2/n2_1/").status_code == 200
            assert cli.get("/n2/n2_1/").status_code == 200
            assert cli.get("/n2/n2_1/").status_code == 429
            # almost there..
            # application: active, default: active (1/minute), ancestors: exempt
            assert cli.get("/n2/n2_1/n2_1_1/").status_code == 200
            assert cli.get("/n2/n2_1/n2_1_1/").status_code == 429
            timeline.forward(60)
            assert cli.get("/n2/n2_1/n2_1_1/").status_code == 200
            assert cli.get("/n2/n2_1/n2_1_1/").status_code == 429
            timeline.forward(60)
            # application limit (5/day) gets this one.
            assert cli.get("/n2/n2_1/n2_1_1/").status_code == 429
            # but not those exempt from application limits
            assert cli.get("/n1/").status_code == 200
            assert cli.get("/n1/n1_1/").status_code == 200
            assert cli.get("/n1/n1_1/n1_1_1/").status_code == 200
            assert cli.get("/n1/n1_1/n1_1_2/").status_code == 200
            # but doesn't spare the ones that didn't opt out.
            assert cli.get("/").status_code == 429
            assert cli.get("/n2/").status_code == 429


def test_nested_blueprint_exemption_child_only(extension_factory):
    app, limiter = extension_factory(default_limits=["1/minute"])
    parent_bp = Blueprint("parent", __name__, url_prefix="/parent")
    child_bp = Blueprint("child", __name__, url_prefix="/child")

    limiter.exempt(child_bp)

    @app.route("/")
    def root():
        return "42"

    @parent_bp.route("/")
    def parent():
        return "41"

    @child_bp.route("/")
    def child():
        return "40"

    parent_bp.register_blueprint(child_bp)
    app.register_blueprint(parent_bp)
    app.register_blueprint(child_bp)  # weird

    with app.test_client() as cli:
        assert cli.get("/").status_code == 200
        assert cli.get("/").status_code == 429
        assert cli.get("/parent/").status_code == 200
        assert cli.get("/parent/").status_code == 429
        assert cli.get("/parent/child/").status_code == 200
        assert cli.get("/parent/child/").status_code == 200
        assert cli.get("/child/").status_code == 200
        assert cli.get("/child/").status_code == 200


def test_nested_blueprint_child_explicit_limit(extension_factory):
    app, limiter = extension_factory(default_limits=["1/minute"])
    parent_bp = Blueprint("parent", __name__, url_prefix="/parent")
    child_bp = Blueprint("child", __name__, url_prefix="/child")

    limiter.limit("2/minute")(child_bp)

    @app.route("/")
    def root():
        return "42"

    @parent_bp.route("/")
    def parent():
        return "41"

    @child_bp.route("/")
    def child():
        return "40"

    parent_bp.register_blueprint(child_bp)
    app.register_blueprint(parent_bp)

    with app.test_client() as cli:
        assert cli.get("/").status_code == 200
        assert cli.get("/").status_code == 429
        assert cli.get("/parent/").status_code == 200
        assert cli.get("/parent/").status_code == 429
        assert cli.get("/parent/child/").status_code == 200
        assert cli.get("/parent/child/").status_code == 200
        assert cli.get("/parent/child/").status_code == 429


def test_nested_blueprint_child_explicit_nested_limits(extension_factory):
    app, limiter = extension_factory(default_limits=["1/minute"])
    parent_bp = Blueprint("parent", __name__, url_prefix="/parent")
    child_bp = Blueprint("child", __name__, url_prefix="/child")
    grand_child_bp = Blueprint("grand_child", __name__, url_prefix="/grand_child")

    limiter.limit("3/hour")(parent_bp)
    limiter.limit("2/minute")(child_bp)
    limiter.limit("5/day", override_defaults=False)(grand_child_bp)

    @app.route("/")
    def root():
        return "42"

    @parent_bp.route("/")
    def parent():
        return "41"

    @child_bp.route("/")
    def child():
        return "40"

    @grand_child_bp.route("/")
    def grand_child():
        return "39"

    child_bp.register_blueprint(grand_child_bp)
    parent_bp.register_blueprint(child_bp)
    app.register_blueprint(parent_bp)

    with hiro.Timeline() as timeline:
        with app.test_client() as cli:
            assert cli.get("/").status_code == 200
            assert cli.get("/").status_code == 429
            assert cli.get("/parent/").status_code == 200
            assert cli.get("/parent/").status_code == 200
            assert cli.get("/parent/").status_code == 200
            assert cli.get("/parent/").status_code == 429
            assert cli.get("/parent/child/").status_code == 200
            assert cli.get("/parent/child/").status_code == 200
            assert cli.get("/parent/child/").status_code == 429
            timeline.forward(datetime.timedelta(minutes=1))
            assert cli.get("/parent/child/").status_code == 200
            # parent's limit is ignored as override_defaults is True by default
            assert cli.get("/parent/child/").status_code == 200
            assert cli.get("/parent/child/grand_child/").status_code == 200
            # global limit is ignored as parent override's default
            assert cli.get("/parent/child/grand_child/").status_code == 200
            # child's limit is not ignored as grandchild sets override default to False
            assert cli.get("/parent/child/grand_child/").status_code == 429
            timeline.forward(datetime.timedelta(minutes=1))
            assert cli.get("/parent/child/grand_child/").status_code == 200
            assert cli.get("/parent/child/grand_child/").status_code == 429
            timeline.forward(datetime.timedelta(minutes=60))
            assert cli.get("/parent/child/grand_child/").status_code == 200
            timeline.forward(datetime.timedelta(minutes=60))
            assert cli.get("/parent/child/grand_child/").status_code == 200
            timeline.forward(datetime.timedelta(minutes=60))
            # grand child's own limit kicks in
            assert cli.get("/parent/child/grand_child/").status_code == 429


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
    caplog.set_level(logging.INFO)
    app = Flask(__name__)
    limiter = Limiter(get_remote_address, app=app, default_limits=["1/second"])
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
    assert "failed to load" in caplog.records[0].msg
    assert "exceeded at endpoint" in caplog.records[-1].msg


def test_invalid_decorated_dynamic_limits_blueprint(caplog):
    caplog.set_level(logging.INFO)
    app = Flask(__name__)
    app.config.setdefault("X", "2 per sec")
    limiter = Limiter(get_remote_address, app=app, default_limits=["1/second"])
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
