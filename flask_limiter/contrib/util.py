from flask import request


def get_remote_address_cloudflare() -> str:
    """
    :return: the ip address for the current request from the CF-Connecting-IP header
     (or 127.0.0.1 if none found)

    """
    return request.headers["CF-Connecting-IP"] or "127.0.0.1"

def get_remote_address_gcp() -> str:
    """
    :return: the ip address for the current request from the X-Forwarded-For header
     (or 127.0.0.1 if none found)

    """
    x_forwarded_for = request.headers.get('X-Forwarded-For')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.remote_addr or "127.0.0.1"
    return ip
