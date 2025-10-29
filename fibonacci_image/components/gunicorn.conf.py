from server_init import *

# Do some pre-flight stuff
create_tls_materials()

# Configure settings
# API app
wsgi_app = f'{API}:app'

# Workers
workers = WORKERS

# Output handling
capture_output = True
loglevel = 'debug'

# Set listening socket
bind = f'{NETWORK_SELF_ADDRESS_LISTENING}:{NETWORK_SELF_PORT}'

# SSL Enabling; Default standard is TLSv2
keyfile = SECRET_KEY_TARGET
certfile = SECRET_CERT_TARGET
ca_certs = TLS_CA_CERT_PATH
do_handshake_on_connect = True
