import string
import random
from urllib.parse import urlparse
from flask import request

def generate_short_code(length=6):
    """Generate a random short code using base62 characters"""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def is_valid_url(url):
    """Validate if the provided string is a valid URL"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def get_client_ip():
    """Get client's IP address, considering proxies"""
    if request.environ.get('HTTP_X_FORWARDED_FOR'):
        return request.environ['HTTP_X_FORWARDED_FOR'].split(',')[0]
    elif request.environ.get('HTTP_X_REAL_IP'):
        return request.environ.get('HTTP_X_REAL_IP')
    else:
        return request.environ.get('REMOTE_ADDR')