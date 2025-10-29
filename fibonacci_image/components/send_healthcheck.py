from server_init import (NETWORK_SELF_ADDRESS_HEALTHCHECK, NETWORK_SELF_PORT, SECRET_CERT_TARGET, SECRET_KEY_TARGET,
                         TLS_CA_CERT_PATH)
from requests import request, Response

# Send healthcheck to self
response: Response = request(
    method='GET',
    url=f'https://{NETWORK_SELF_ADDRESS_HEALTHCHECK}:{NETWORK_SELF_PORT}/healthcheck',
    cert=(SECRET_CERT_TARGET, SECRET_KEY_TARGET),
    verify=TLS_CA_CERT_PATH
)
