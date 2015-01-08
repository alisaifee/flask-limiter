"""

"""

from flask import request


def get_ipaddr():
    """
    :return: the ip address for the current request (or 127.0.0.1 if none found)
    """
    if request.access_route:
        return request.access_route[0]
    else:
        return request.remote_addr or '127.0.0.1'