import sys


def test_import():
    import flask_limiter

def test_module_version():
    import flask_limiter
    assert flask_limiter.__version__ is not None

