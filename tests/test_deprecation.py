"""

"""
import unittest

import pytest

from flask import Flask
from flask_limiter import Limiter


class DeprecationTests(unittest.TestCase):
    def test_insecure_setup(self):
        app = Flask(__name__)
        with pytest.warns(UserWarning) as record:
            Limiter(app)
            self.assertRegex(
                record[0].message.args[0],
                "Use of the default `get_ipaddr`"
            )

    def test_with_global_limits(self):
        app = Flask(__name__)
        with pytest.warns(UserWarning) as record:
            Limiter(
                app,
                key_func=lambda x: 'test', global_limits=['1/second']
            )
            self.assertRegex(
                record[0].message.args[0],
                "global_limits was a badly named configuration",
            )
