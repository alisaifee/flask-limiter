from functools import wraps
import platform
from nose.plugins.skip import SkipTest


def test_import():
    import flask_limiter


def test_module_version():
    import flask_limiter
    assert flask_limiter.__version__ is not None


def skip_if_pypy(fn):
    @wraps(fn)
    def __inner(*a, **k):
        if platform.python_implementation().lower() == "pypy":
            raise SkipTest
        return fn(*a, **k)

    return __inner
