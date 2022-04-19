from __future__ import annotations

from flask import request


def get_remote_address() -> str:
    """
    :return: the ip address for the current request
     (or 127.0.0.1 if none found)

    """
    return request.remote_addr or "127.0.0.1"
