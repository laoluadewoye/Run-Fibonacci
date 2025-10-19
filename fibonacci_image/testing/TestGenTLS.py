from cryptography import x509
from cryptography.x509.oid import NameOID
from pathlib import Path
from GenerateTLS import create_key_cert
from itertools import product
from ipaddress import ip_address, IPv4Address

# Get base folder
BASE_FOLDER = Path(__file__).resolve().parent

# Generate CA TLS materials
print('Creating CA TLS materials...')
ca_cert_name: str = 'ca.test.com'
ca_alt_names: list[str] = [ca_cert_name, 'test.com', 'localhost']
ca_subject: x509.Name = x509.Name([
    x509.NameAttribute(NameOID.COUNTRY_NAME, 'US'),
    x509.NameAttribute(NameOID.COMMON_NAME, ca_cert_name),
])
ca_key, ca_cert = create_key_cert(
    subject=ca_subject, san_names=ca_alt_names, san_ips=['127.0.0.1'], cert_days=2, public_exponent=65537,
    key_length=4096, filename=f'{BASE_FOLDER}/test_ca', key_ext='key', cert_ext='crt', pem_ext='pem', is_ca=True,
    is_cert_signer=True
)

# Generate external TLS materials
apis: list[str] = ['rest']
platforms: list[str] = ['alma', 'alpine']
datastores: list[str] = ['none', 'file', 'elasticstack', 'mongodb', 'postgresql']
test_combos = product(apis, platforms, datastores)

current_ip: IPv4Address = ip_address('172.20.0.2')
external_alt_ips: list[str] = ['127.0.0.1', '172.20.0.1']

for api, platform, datastore in test_combos:
    # Limit to how high the last byte can be
    if int(str(current_ip).split('.')[-1]) >= 224:
        current_ip += ip_address(f'172.20.{int(str(current_ip).split('.')[-2]) + 1}.1')

    # Add addresses
    if datastore == 'elasticstack':
        external_alt_ips.extend([str(current_ip + i) for i in range(3)])
        current_ip += 3
    elif datastore == 'mongodb':
        external_alt_ips.extend([str(current_ip + i) for i in range(2)])
        current_ip += 2
    elif datastore == 'postgresql':
        external_alt_ips.extend([str(current_ip + i) for i in range(2)])
        current_ip += 2
    else:
        external_alt_ips.append(str(current_ip))
        current_ip += 1

print('Creating external TLS materials...')
external_cert_name: str = 'external.test.com'
external_alt_names: list[str] = [external_cert_name, 'test.com', 'localhost']
external_subject: x509.Name = x509.Name([
    x509.NameAttribute(NameOID.COUNTRY_NAME, 'US'),
    x509.NameAttribute(NameOID.COMMON_NAME, external_cert_name),
])
external_key, external_cert = create_key_cert(
    subject=external_subject, san_names=external_alt_names, san_ips=external_alt_ips, cert_days=1,
    public_exponent=65537, key_length=4096, filename=f'{BASE_FOLDER}/test_self', key_ext='key', cert_ext='crt',
    pem_ext='pem', issuer_key=ca_key, issuer_cert=ca_cert, ca_suffix='ca', is_key_encrypter=True
)
