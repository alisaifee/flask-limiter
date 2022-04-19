from flask import Blueprint, Flask, request
from flask.views import View

import flask_limiter
from flask_limiter import ExemptionScope, Limiter
from flask_limiter.util import get_remote_address


def app():
    def default_limit_extra():
        if request.headers.get("X-Evil"):
            return "100/minute"
        return "200/minute"

    def default_cost():
        if request.headers.get("X-Evil"):
            return 2
        return 1

    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["10/second", "1000/hour", default_limit_extra],
        default_limits_exempt_when=lambda: request.headers.get("X-Internal"),
        default_limits_deduct_when=lambda response: response.status_code == 200,
        default_limits_cost=default_cost,
        application_limits=["5000/hour"],
        headers_enabled=True,
    )

    app = Flask(__name__)
    app.config.from_prefixed_env()

    @app.route("/")
    def root():
        return "42"

    @app.route("/version")
    @limiter.exempt
    def version():
        return flask_limiter.__version__

    health_blueprint = Blueprint("health", __name__, url_prefix="/health")

    @health_blueprint.route("/")
    def health():
        return "ok"

    app.register_blueprint(health_blueprint)

    limiter.exempt(
        health_blueprint,
        flags=ExemptionScope.DEFAULT
        | ExemptionScope.APPLICATION
        | ExemptionScope.ANCESTORS,
    )

    class ResourceView(View):
        methods = ["GET", "POST"]
        decorators = [limiter.limit("5/second", per_method=True)]

        def dispatch_request(self):
            return request.method.lower()

    app.add_url_rule("/resource", view_func=ResourceView.as_view("resource"))

    limiter.init_app(app)

    return app


if __name__ == "__main__":
    app().run()
