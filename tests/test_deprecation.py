"""

"""
import unittest
import warnings


class DeprecationTests(unittest.TestCase):
    def test_insecure_setup(self):
        with warnings.catch_warnings(record=True) as w:
            from flask import Flask
            from flask_limiter import Limiter
            app = Flask(__name__)
            Limiter(app)
            self.assertEqual(len(w), 1)

    def test_with_global_limits(self):
        with warnings.catch_warnings(record=True) as w:
            from flask import Flask
            from flask_limiter import Limiter
            app = Flask(__name__)
            Limiter(app, key_func = lambda x: 'test', global_limits=['1/second'])
            self.assertEqual(len(w), 1)
