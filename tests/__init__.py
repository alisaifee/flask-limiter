import sys
import time


def test_import():
    import flask_limiter

def test_module_version():
    import flask_limiter
    assert flask_limiter.__version__ is not None

def sleep_upto(amount, start, total):
    if time.time() - start >= total:
        return
    else:
        time.sleep(amount)
