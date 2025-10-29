from os import environ
from json import load
from copy import deepcopy
from collections.abc import Iterator
from typing import Any
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from cryptography import x509
from cryptography.x509.oid import NameOID
from ipaddress import ip_address
from datetime import datetime, timedelta, timezone


def get_all_settings(cur_config: dict, prefix: str = '') -> Iterator[str]:
    for key, value in cur_config.items():
        if isinstance(value, dict):
            yield f'{prefix}{key}.'
            yield from get_all_settings(value, f'{prefix}{key}.')
        else:
            yield f'{prefix}{key}'


def access_nested_setting(cur_config: dict, key_string: str, new_value=None) -> Any:
    # Setup keys
    keys: list[str] = key_string.split('.')
    last_key: str = key_string

    # Setup dictionaries
    current: dict = cur_config
    last_current: dict = current

    # Loop through dictionary
    try:
        for key in keys:
            last_key = key
            last_current = current
            current = current[key]

        if new_value is not None:
            last_current[last_key] = new_value
            return None
        else:
            return current
    except (KeyError, TypeError):
        return None


def create_key_cert(subject: x509.Name, san_names: list[str], san_ips: list[str], cert_days: int, public_exponent: int,
                    key_length: int, filename: str, key_ext: str, cert_ext: str, pem_ext: str, issuer_key=None,
                    issuer_cert=None, is_ca: bool = False, ca_suffix: str = '', is_key_encrypter: bool = False,
                    is_cert_signer: bool = False) -> tuple:
    # Create key
    key: RSAPrivateKey = rsa.generate_private_key(public_exponent=public_exponent, key_size=key_length)

    # Create certificate and set up names
    cert = x509.CertificateBuilder()
    if is_ca:
        cert = cert.subject_name(subject)
        cert = cert.issuer_name(subject)
    else:
        cert = cert.subject_name(subject)
        cert = cert.issuer_name(issuer_cert.subject)

    # Add core cert information
    cert = cert.public_key(key.public_key())
    cert = cert.serial_number(x509.random_serial_number())
    cert = cert.not_valid_before(datetime.now(timezone.utc))
    cert = cert.not_valid_after(datetime.now(timezone.utc) + timedelta(days=cert_days))

    # Add extensions
    formatted_san_names = [x509.DNSName(san_name) for san_name in san_names]
    formatted_san_names.extend([x509.IPAddress(ip_address(san_ip)) for san_ip in san_ips])
    cert = cert.add_extension(x509.SubjectAlternativeName(formatted_san_names), critical=False)
    cert = cert.add_extension(x509.BasicConstraints(ca=is_ca, path_length=None), critical=True)
    cert = cert.add_extension(
        x509.KeyUsage(
            digital_signature=True, content_commitment=False, key_encipherment=is_key_encrypter,
            data_encipherment=False, key_agreement=False, key_cert_sign=is_cert_signer, crl_sign=True,
            encipher_only=False, decipher_only=False,
        ),
        critical=True
    )
    cert = cert.add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)

    # Add additional extensions if needed
    if not is_ca:
        cert = cert.add_extension(
            x509.ExtendedKeyUsage([x509.ExtendedKeyUsageOID.CLIENT_AUTH, x509.ExtendedKeyUsageOID.SERVER_AUTH,]),
            critical=False
        )
        cert = cert.add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_subject_key_identifier(
                issuer_cert.extensions.get_extension_for_class(x509.SubjectKeyIdentifier).value
            ),
            critical=False
        )

    # Sign certificate
    if is_ca:
        cert = cert.sign(key, hashes.SHA512())
    else:
        cert = cert.sign(issuer_key, hashes.SHA512())

    # Save key and certificate as various documents
    key_str: str = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()
    ).decode()
    cert_str: str = cert.public_bytes(serialization.Encoding.PEM).decode()

    with open(f'{filename}.{key_ext}', 'w') as key_file:
        key_file.write(key_str)

    with open(f'{filename}.{cert_ext}', 'w') as cert_file:
        cert_file.write(cert_str)

    with open(f'{filename}.{pem_ext}', 'w') as pem_file:
        pem_file.write(f'{cert_str}\n{key_str}')

    if not is_ca:
        issuer_cert_str = issuer_cert.public_bytes(serialization.Encoding.PEM).decode()
        with open(f'{filename}-{ca_suffix}.{cert_ext}', 'w') as cert_combo_file:
            cert_combo_file.write(f'{cert_str}\n{issuer_cert_str}')

    return key, cert


# Import server configurations
with open(environ.get('SERVER_CONFIG_FILEPATH')) as config_file:
    server_config: dict = load(config_file)

if environ.get('SERVER_CONFIG_FILEPATH') == environ.get('DEFAULT_SERVER_CONFIG_FILEPATH'):
    default_config: dict = server_config
    config_mod_src: str = "default"
else:
    with open(environ.get('DEFAULT_SERVER_CONFIG_FILEPATH')) as default_file:
        default_config: dict = load(default_file)
    config_mod_src: str = "custom"

# Create the runtime configuration
settings: list[str] = [config for config in get_all_settings(default_config)]
RUNTIME_CONFIG: dict = deepcopy(default_config)
for setting_string in settings:
    # Skip parent keys
    if setting_string.endswith('.'):
        continue

    # Gather all settings
    default_setting: Any = access_nested_setting(default_config, setting_string)
    server_setting: Any = access_nested_setting(server_config, setting_string)
    env_setting: Any = environ.get(setting_string.replace('.', '_').upper(), None)

    # Make modifications to final setting
    if env_setting is not None:
        print(f'Setting {setting_string} from environment...', flush=True)
        access_nested_setting(RUNTIME_CONFIG, setting_string, new_value=env_setting)
    elif server_setting is not None:
        print(f'Setting {setting_string} from {config_mod_src} configuration...', flush=True)
        access_nested_setting(RUNTIME_CONFIG, setting_string, new_value=server_setting)
    elif default_setting is None:
        raise KeyError(f'{setting_string} does not exist in default configuration.')

# Create constants for server
# Set API
API: str = RUNTIME_CONFIG['api']

# Set datastore
DATASTORE_AUTH_USERNAME: str = RUNTIME_CONFIG['datastore']['auth']['username']
DATASTORE_AUTH_PASSWORD: str = RUNTIME_CONFIG['datastore']['auth']['password']
DATASTORE_LOGS_DEFAULT_PATH: str = RUNTIME_CONFIG['datastore']['logs']['defaultPath']
DATASTORE_LOGS_OPERATION_PATH: str = RUNTIME_CONFIG['datastore']['logs']['operationPath']
DATASTORE_LOGS_SERVER_PATH: str = RUNTIME_CONFIG['datastore']['logs']['serverPath']
DATASTORE_TYPE: str = RUNTIME_CONFIG['datastore']['type']

# Set datastore socket
NETWORK_DATASTORE_ADDRESS: str = RUNTIME_CONFIG['network']['datastore']['address']
NETWORK_DATASTORE_PORT: int = int(RUNTIME_CONFIG['network']['datastore']['port'])

# Set destination socket
NETWORK_DEST_ADDRESS: str = RUNTIME_CONFIG['network']['dest']['address']
NETWORK_DEST_PORT: int = int(RUNTIME_CONFIG['network']['dest']['port'])

# Set self server sockets
NETWORK_SELF_ADDRESS_HEALTHCHECK: str = RUNTIME_CONFIG['network']['self']['address']['healthcheck']
NETWORK_SELF_ADDRESS_LISTENING: str = RUNTIME_CONFIG['network']['self']['address']['listening']
NETWORK_SELF_PORT: int = int(RUNTIME_CONFIG['network']['self']['port'])

# Set server stage information
STAGE_COUNT: int = int(RUNTIME_CONFIG['stage']['count'])
STAGE_INDEX: int = int(RUNTIME_CONFIG['stage']['index'])

# Set other server settings
THROTTLE_SECONDS: int = int(RUNTIME_CONFIG['throttleSecs'])
UPPER_BOUND: int = int(RUNTIME_CONFIG['upperBound'])
WORKERS: int = int(RUNTIME_CONFIG['workers'])

# Set CA locations
TLS_CA_KEY_PATH: str = RUNTIME_CONFIG['tls']['ca']['keyPath']
TLS_CA_CERT_PATH: str = RUNTIME_CONFIG['tls']['ca']['certPath']

# Set TLS creation settings
TLS_GEN_CA_SUFFIX: str = RUNTIME_CONFIG['tls']['gen']['caSuffix']
TLS_GEN_CERT_DAYS: int = int(RUNTIME_CONFIG['tls']['gen']['certDays'])
TLS_GEN_EXT_CERT: str = RUNTIME_CONFIG['tls']['gen']['ext']['cert']
TLS_GEN_EXT_KEY: str = RUNTIME_CONFIG['tls']['gen']['ext']['key']
TLS_GEN_EXT_PEM: str = RUNTIME_CONFIG['tls']['gen']['ext']['pem']
TLS_GEN_KEY_LENGTH: int = int(RUNTIME_CONFIG['tls']['gen']['keyLength'])
TLS_GEN_PUBLIC_EXPONENT: int = int(RUNTIME_CONFIG['tls']['gen']['pubExponent'])
TLS_GEN_SECRET_TARGET: str = RUNTIME_CONFIG['tls']['gen']['secretTarget']

# Set Subject Alternative Names
TLS_SAN_IPS: str = RUNTIME_CONFIG['tls']['san']['ips']
TLS_SAN_NAMES: str = RUNTIME_CONFIG['tls']['san']['names']

# Set generated TLS targets
SECRET_KEY_TARGET: str = f'{TLS_GEN_SECRET_TARGET}.{TLS_GEN_EXT_KEY}'
SECRET_CERT_TARGET: str = f'{TLS_GEN_SECRET_TARGET}.{TLS_GEN_EXT_CERT}'
SECRET_PEM_TARGET: str = f'{TLS_GEN_SECRET_TARGET}.{TLS_GEN_EXT_PEM}'


def create_tls_materials():
    # Read in CA TLS materials
    with open(TLS_CA_KEY_PATH, 'rb') as ca_key_file:
        ca_key = serialization.load_pem_private_key(ca_key_file.read(), None)

    with open(TLS_CA_CERT_PATH, 'rb') as ca_cert_file:
        ca_cert = x509.load_pem_x509_certificate(ca_cert_file.read())

    # Create Server TLS materials
    external_alt_ips: list[str] = TLS_SAN_IPS.split(',')
    external_alt_names: list[str] = TLS_SAN_NAMES.split(',')
    external_subject: x509.Name = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, 'US'),
        x509.NameAttribute(NameOID.COMMON_NAME, external_alt_names[0]),
    ])
    create_key_cert(
        subject=external_subject, san_names=external_alt_names, san_ips=external_alt_ips, cert_days=TLS_GEN_CERT_DAYS,
        public_exponent=TLS_GEN_PUBLIC_EXPONENT, key_length=TLS_GEN_KEY_LENGTH, filename=TLS_GEN_SECRET_TARGET,
        key_ext=TLS_GEN_EXT_KEY, cert_ext=TLS_GEN_EXT_CERT, pem_ext=TLS_GEN_EXT_PEM, issuer_key=ca_key,
        issuer_cert=ca_cert, ca_suffix=TLS_GEN_CA_SUFFIX, is_key_encrypter=True
    )
