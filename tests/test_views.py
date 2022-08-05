import flask_restful
import hiro
import pytest
from flask import request
from flask.views import MethodView, View


def test_pluggable_views(extension_factory):
    app, limiter = extension_factory(default_limits=["1/hour"])

    class Va(View):
        methods = ["GET", "POST"]
        decorators = [limiter.limit("2/second")]

        def dispatch_request(self):
            return request.method.lower()

    class Vb(View):
        methods = ["GET"]
        decorators = [limiter.limit("1/second, 3/minute")]

        def dispatch_request(self):
            return request.method.lower()

    class Vc(View):
        methods = ["GET"]

        def dispatch_request(self):
            return request.method.lower()

    app.add_url_rule("/a", view_func=Va.as_view("a"))
    app.add_url_rule("/b", view_func=Vb.as_view("b"))
    app.add_url_rule("/c", view_func=Vc.as_view("c"))
    with hiro.Timeline().freeze() as timeline:
        with app.test_client() as cli:
            assert 200 == cli.get("/a").status_code
            assert 200 == cli.get("/a").status_code
            assert 429 == cli.post("/a").status_code
            assert 200 == cli.get("/b").status_code
            timeline.forward(1)
            assert 200 == cli.get("/b").status_code
            timeline.forward(1)
            assert 200 == cli.get("/b").status_code
            timeline.forward(1)
            assert 429 == cli.get("/b").status_code
            assert 200 == cli.get("/c").status_code
            assert 429 == cli.get("/c").status_code


def test_pluggable_method_views(extension_factory):
    app, limiter = extension_factory(default_limits=["1/hour"])

    class Va(MethodView):
        decorators = [limiter.limit("2/second")]

        def get(self):
            return request.method.lower()

        def post(self):
            return request.method.lower()

    class Vb(MethodView):
        decorators = [limiter.limit("1/second, 3/minute")]

        def get(self):
            return request.method.lower()

    class Vc(MethodView):
        def get(self):
            return request.method.lower()

    class Vd(MethodView):
        decorators = [limiter.limit("1/minute", methods=["get"])]

        def get(self):
            return request.method.lower()

        def post(self):
            return request.method.lower()

    app.add_url_rule("/a", view_func=Va.as_view("a"))
    app.add_url_rule("/b", view_func=Vb.as_view("b"))
    app.add_url_rule("/c", view_func=Vc.as_view("c"))
    app.add_url_rule("/d", view_func=Vd.as_view("d"))

    with hiro.Timeline().freeze() as timeline:
        with app.test_client() as cli:
            assert 200 == cli.get("/a").status_code
            assert 200 == cli.get("/a").status_code
            assert 429 == cli.get("/a").status_code
            assert 429 == cli.post("/a").status_code
            assert 200 == cli.get("/b").status_code
            timeline.forward(1)
            assert 200 == cli.get("/b").status_code
            timeline.forward(1)
            assert 200 == cli.get("/b").status_code
            timeline.forward(1)
            assert 429 == cli.get("/b").status_code
            assert 200 == cli.get("/c").status_code
            assert 429 == cli.get("/c").status_code
            assert 200 == cli.get("/d").status_code
            assert 429 == cli.get("/d").status_code
            assert 200 == cli.post("/d").status_code
            assert 429 == cli.post("/d").status_code
            timeline.forward(3600)
            assert 200 == cli.post("/d").status_code


def test_flask_restful_resource(extension_factory):
    app, limiter = extension_factory(default_limits=["1/hour"])
    api = flask_restful.Api(app)

    class Va(flask_restful.Resource):
        decorators = [limiter.limit("2/second")]

        def get(self):
            return request.method.lower()

        def post(self):
            return request.method.lower()

    class Vb(flask_restful.Resource):
        decorators = [limiter.limit("1/second, 3/minute")]

        def get(self):
            return request.method.lower()

    class Vc(flask_restful.Resource):
        def get(self):
            return request.method.lower()

    class Vd(flask_restful.Resource):
        decorators = [
            limiter.limit("2/second", methods=["GET"]),
            limiter.limit("1/second", methods=["POST"]),
        ]

        def get(self):
            return request.method.lower()

        def post(self):
            return request.method.lower()

    api.add_resource(Va, "/a")
    api.add_resource(Vb, "/b")
    api.add_resource(Vc, "/c")
    api.add_resource(Vd, "/d")

    with hiro.Timeline().freeze() as timeline:
        with app.test_client() as cli:
            assert 200 == cli.get("/a").status_code
            assert 200 == cli.get("/a").status_code
            assert 429 == cli.get("/a").status_code
            assert 429 == cli.post("/a").status_code
            assert 200 == cli.get("/b").status_code
            assert 200 == cli.get("/d").status_code
            assert 200 == cli.get("/d").status_code
            assert 429 == cli.get("/d").status_code
            assert 200 == cli.post("/d").status_code
            assert 429 == cli.post("/d").status_code
            timeline.forward(1)
            assert 200 == cli.get("/b").status_code
            timeline.forward(1)
            assert 200 == cli.get("/b").status_code
            timeline.forward(1)
            assert 429 == cli.get("/b").status_code
            assert 200 == cli.get("/c").status_code
            assert 429 == cli.get("/c").status_code


@pytest.mark.xfail
def test_flask_restx_resource(extension_factory):
    import flask_restx

    app, limiter = extension_factory()
    api = flask_restx.Api(app)
    ns = api.namespace("test")

    @ns.route("/a")
    class Va(flask_restx.Resource):
        decorators = [limiter.limit("2/second", per_method=True)]

        def get(self):
            return request.method.lower()

        def post(self):
            return request.method.lower()

    with hiro.Timeline().freeze() as timeline:
        with app.test_client() as cli:
            assert 200 == cli.get("/test/a").status_code
            assert 200 == cli.get("/test/a").status_code
            assert 200 == cli.post("/test/a").status_code
            assert 200 == cli.post("/test/a").status_code
            assert 429 == cli.get("/test/a").status_code
            assert 429 == cli.post("/test/a").status_code
            timeline.forward(1)
            assert 200 == cli.get("/test/a").status_code
            assert 200 == cli.post("/test/a").status_code
