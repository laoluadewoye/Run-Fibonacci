from os import environ

# Assert variables exist
assert 'SERVER_API' in environ
assert 'SERVER_STAGE_COUNT' in environ
assert 'SELF_LISTENING_ADDRESS' in environ
assert 'SELF_PORT' in environ
assert 'SECRET_KEY_TARGET' in environ
assert 'SECRET_CERT_TARGET' in environ
assert 'SECRET_CA_CERT_TARGET' in environ

# API app
wsgi_app = f'{environ.get('SERVER_API')}:app'

# Workers
workers = int(environ.get('SERVER_STAGE_COUNT')) * 2 + 1

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
