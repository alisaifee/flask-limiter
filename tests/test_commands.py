import os
import re

import pytest
from flask import Flask

from flask_limiter.commands import cli


@pytest.fixture(autouse=True)
def set_env():
    os.environ["NO_COLOR"] = "True"


def test_no_limiter(kitchensink_factory):
    app = Flask(__name__)
    runner = app.test_cli_runner()
    result = runner.invoke(cli, ["config"])
    assert "No Flask-Limiter extension installed" in result.output
    result = runner.invoke(cli, ["limits"])
    assert "No Flask-Limiter extension installed" in result.output


def test_config(kitchensink_factory):
    app, limiter = kitchensink_factory()
    runner = app.test_cli_runner()
    result = runner.invoke(cli, ["config"])
    assert re.compile("Enabled.*True").search(result.output)


def test_no_config(extension_factory):
    app, limiter = extension_factory()
    runner = app.test_cli_runner()
    result = runner.invoke(cli, ["config"])
    assert re.compile("Enabled.*True").search(result.output)


def test_limits(kitchensink_factory):
    app, limiter = kitchensink_factory()
    runner = app.test_cli_runner()
    result = runner.invoke(cli, ["limits"])
    assert "5000 per 1 hour" in result.output
    assert re.compile(r"health.health: /health/\n\s*└── Exempt", re.MULTILINE).search(
        result.output
    )


def test_limits_filter_endpoint(kitchensink_factory):
    app, limiter = kitchensink_factory()
    runner = app.test_cli_runner()
    result = runner.invoke(cli, ["limits", "--endpoint=root"])
    assert "root: /" in result.output
    result = runner.invoke(cli, ["limits", "--endpoint=groot"])
    assert "groot not found" in result.output


def test_limits_filter_path(kitchensink_factory):
    app, limiter = kitchensink_factory()
    runner = app.test_cli_runner()
    result = runner.invoke(cli, ["limits", "--path=/"])
    assert "root: /" in result.output
    result = runner.invoke(cli, ["limits", "--path=/", "--method=POST"])
    assert "POST: / could not be matched" in result.output
    result = runner.invoke(cli, ["limits", "--path=/groot"])
    assert "groot could not be matched" in result.output


def test_limits_with_test(kitchensink_factory, mocker):
    app, limiter = kitchensink_factory()
    runner = app.test_cli_runner()
    mt = mocker.spy(limiter.limiter, "test")
    mw = mocker.spy(limiter.limiter, "get_window_stats")
    result = runner.invoke(cli, ["limits", "--key=127.0.0.1"])
    assert "5000 per 1 hour: Pass (5000 out of 5000 remaining)" in result.output
    mt.side_effect = lambda *a: False
    mw.side_effect = lambda *a: (0, 0)
    result = runner.invoke(cli, ["limits", "--key=127.0.0.1"])
    assert "5000 per 1 hour: Fail (0 out of 5000 remaining)" in result.output
    assert re.compile(r"health.health: /health/\n\s*└── Exempt", re.MULTILINE).search(
        result.output
    )


def test_limits_with_test_storage_down(kitchensink_factory, mocker):
    app, limiter = kitchensink_factory()
    ms = mocker.spy(list(app.extensions.get("limiter"))[0].storage, "check")
    ms.side_effect = lambda: False
    runner = app.test_cli_runner()
    result = runner.invoke(cli, ["limits", "--key=127.0.0.1"])
    assert "Storage not available" in result.output
    result = runner.invoke(cli, ["config"])
    assert re.compile("└── Status.*└── Error").search(result.output)


def test_clear_limits_no_extension():
    app = Flask(__name__)
    runner = app.test_cli_runner()
    result = runner.invoke(cli, ["clear", "--key=127.0.0.1", "-y"])
    assert "No Flask-Limiter extension installed" in result.output


def test_clear_limits(kitchensink_factory, redis_connection):
    app, limiter = kitchensink_factory(storage_uri="redis://localhost:46379")
    runner = app.test_cli_runner()
    with app.test_client() as client:
        [client.get("/") for _ in range(5)]
        [client.get("/resource") for _ in range(5)]
        [client.post("/resource") for _ in range(5)]
    result = runner.invoke(cli, ["limits", "--key=127.0.0.1"])
    assert "Fail (0 out of 5 remaining)" in result.output
    result = runner.invoke(cli, ["clear", "--key=127.0.0.1", "-y"])
    assert "5000 per 1 hour: Cleared" in result.output
    assert "5 per 1 second: Cleared" in result.output
    result = runner.invoke(cli, ["clear", "--key=127.0.0.1", "--endpoint=root", "-y"])
    assert "5000 per 1 hour: Cleared" not in result.output
    assert "5 per 1 second: Cleared" not in result.output
    assert "10 per 1 second: Cleared" in result.output
