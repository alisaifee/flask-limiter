"""

"""
import unittest

import mock
from flask import Flask


class DeprecationTests(unittest.TestCase):

    def test_insecure_setup(self):
        with mock.patch("flask.ext.limiter.extension.warnings") as warnings:
            from flask.ext.limiter import Limiter
            app = Flask(__name__)
            Limiter(app)
            self.assertEqual(warnings.warn.call_count, 1)

