import logging

from flask import Flask
from mock import mock

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


class FlaskLimiterTestCase:

    def build_app(self, config={}, **limiter_args):
        app = Flask(__name__)
        for k, v in config.items():
            app.config.setdefault(k, v)
        limiter_args.setdefault('key_func', get_remote_address)
        limiter = Limiter(app, **limiter_args)
        mock_handler = mock.Mock()
        mock_handler.level = logging.INFO
        limiter.logger.addHandler(mock_handler)
        return app, limiter
