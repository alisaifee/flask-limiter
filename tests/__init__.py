import platform
from nose.plugins.skip import SkipTest

def test_import():
    import flask_limiter

def test_module_version():
    import flask_limiter
    assert flask_limiter.__version__ is not None


def skip_if_pypy(_):
    def __inner(**_):
        if platform.python_implementation().lower() == "pypy":
            raise SkipTest
    return __inner
