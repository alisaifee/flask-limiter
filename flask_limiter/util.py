from flask import request


def get_remote_address() -> str:
    """
    :return: the ip address for the current request
     (or 127.0.0.1 if none found)

    """
    return request.remote_addr or "127.0.0.1"

def get_remote_address_cloudflare():
    """
    :return: the ip address for the current request from the CF-Connecting-IP header
     (or 127.0.0.1 if none found)

    """
    return request.headers['CF-Connecting-IP'] or '127.0.0.1'