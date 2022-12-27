import os
import jinja2
from flask import Blueprint, Flask, jsonify, request, render_template, make_response
from flask.views import View

import flask_limiter
from flask_limiter import ExemptionScope, Limiter
from flask_limiter.util import get_remote_address


def index_error_responder(request_limit):
    error_template = jinja2.Environment().from_string(
        """
    <h1>Breached rate limit of: {{request_limit.limit}}</h1>
    <h2>Path: {{request.path}}</h2>
    """
    )
    return make_response(render_template(error_template, request_limit=request_limit))


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
        get_remote_address,
        default_limits=["20/hour", "1000/hour", default_limit_extra],
        default_limits_exempt_when=lambda: request.headers.get("X-Internal"),
        default_limits_deduct_when=lambda response: response.status_code == 200,
        default_limits_cost=default_cost,
        application_limits=["5000/hour"],
        headers_enabled=True,
        storage_uri=os.environ.get("FLASK_RATELIMIT_STORAGE_URI", "memory://"),
    )

    app = Flask(__name__)
    app.config.from_prefixed_env()

    @app.errorhandler(429)
    def handle_error(e):
        return e.get_response() or make_response(
            jsonify(error="ratelimit exceeded %s" % e.description)
        )

    @app.route("/")
    @limiter.limit("10/minute", on_breach=index_error_responder)
    def root():
        """
        Custom rate limit of 10/minute which overrides the default limits.
        The error page displayed on rate limit breached is also customized by using
        an `on_breach` callback to render a template
        """
        return "42"

    @app.route("/version")
    @limiter.exempt
    def version():
        """
        Exempt from all rate limits
        """
        return flask_limiter.__version__

    health_blueprint = Blueprint("health", __name__, url_prefix="/health")

    @health_blueprint.route("/")
    def health():
        return "ok"

    app.register_blueprint(health_blueprint)

    #: Exempt from default, application and ancestor rate limits (effectively all)
    limiter.exempt(
        health_blueprint,
        flags=ExemptionScope.DEFAULT
        | ExemptionScope.APPLICATION
        | ExemptionScope.ANCESTORS,
    )

    class ResourceView(View):
        methods = ["GET", "POST"]

        @staticmethod
        def json_error_responder(request_limit):
            return jsonify({"limit": str(request_limit.limit)})

        #: Custom rate limit of 5/second by http method type for all routes under this
        #: resource view. The error response is also customized by using the `on_breach`
        #: callback to return a json error response
        decorators = [
            limiter.limit("5/second", per_method=True, on_breach=json_error_responder)
        ]

        def dispatch_request(self):
            return request.method.lower()

    app.add_url_rule("/resource", view_func=ResourceView.as_view("resource"))

    limiter.init_app(app)

    return app


if __name__ == "__main__":
    app().run()
