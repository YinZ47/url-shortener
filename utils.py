import string
import random
import requests
import os
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

def get_ip_location(ip_address):
    """Get geolocation for IP address"""
    api_key = os.environ.get('IPAPI_KEY')
    if not api_key:
        return None
    
    try:
        response = requests.get(
            f'https://ipapi.co/{ip_address}/json/',
            params={'key': api_key},
            timeout=5
        )
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return None