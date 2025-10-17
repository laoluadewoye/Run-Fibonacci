from multiprocessing import cpu_count
from os import environ

# Assert TLS materials exist
assert 'SECRET_KEY_TARGET' in environ
assert 'SECRET_CERT_TARGET' in environ
assert 'SECRET_CA_CERT_TARGET' in environ

# Defaults
wsgi_app = f'{environ.get('SERVER_API')}:app'
workers = cpu_count() * 2 + 1

# Output handling
capture_output = True
loglevel = 'debug'

# Set listening socket
bind = f'{environ.get('SELF_LISTENING_ADDRESS')}:{environ.get('SELF_PORT')}'

# SSL Enabling; Default standard is TLSv2
keyfile = environ.get('SECRET_KEY_TARGET')
certfile = environ.get('SECRET_CERT_TARGET')
ca_certs = environ.get('SECRET_CA_CERT_TARGET')
do_handshake_on_connect = True
