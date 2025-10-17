from os import environ
from requests import request, Response

# Get all constants
SELF_HEALTHCHECK_ADDRESS: str = environ.get('SELF_HEALTHCHECK_ADDRESS')
SELF_PORT: str = environ.get('SELF_PORT')
SECRET_KEY_TARGET: str = environ.get('SECRET_KEY_TARGET')
SECRET_CERT_TARGET: str = environ.get('SECRET_CERT_TARGET')
SECRET_CA_CERT_TARGET: str = environ.get('SECRET_CA_CERT_TARGET')

# Send healthcheck to self
response: Response = request(
    method='GET',
    url=f'https://{SELF_HEALTHCHECK_ADDRESS}:{SELF_PORT}/healthcheck',
    cert=(SECRET_CERT_TARGET, SECRET_KEY_TARGET),
    verify=SECRET_CA_CERT_TARGET
)
