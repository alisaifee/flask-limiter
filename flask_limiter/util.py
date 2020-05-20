""""""

from flask import request


def get_ipaddr():  # pragma: no cover
    """
    :return: the ip address for the current request
     (or 127.0.0.1 if none found) based on the X-Forwarded-For headers.

    .. deprecated:: 0.9.2
     """
    if request.access_route:
        return request.access_route[0]
    else:
        return request.remote_addr or '127.0.0.1'


def get_remote_address():
    """
    :return: the ip address for the current request
     (or 127.0.0.1 if none found)

    """
    return request.remote_addr or '127.0.0.1'
