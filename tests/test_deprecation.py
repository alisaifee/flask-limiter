"""

"""
import unittest

import pytest

from flask import Flask
from flask_limiter import Limiter
import re


class DeprecationTests(unittest.TestCase):
    def test_insecure_setup(self):
        app = Flask(__name__)
        with pytest.warns(UserWarning) as record:
            Limiter(app)
            assert re.search(
                "Use of the default `get_ipaddr`",
                record[0].message.args[0]
            )

    def test_with_global_limits(self):
        app = Flask(__name__)
        with pytest.warns(UserWarning) as record:
            Limiter(
                app,
                key_func=lambda x: 'test', global_limits=['1/second']
            )
            assert re.search(
                "global_limits was a badly named configuration",
                record[0].message.args[0]
            )
