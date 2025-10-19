from cryptography import x509
from cryptography.x509.oid import NameOID
from pathlib import Path
from GenerateTLS import create_key_cert

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
num_combos = len(['rest']) * len(['alma', 'alpine']) * len(['none', 'file'])
external_alt_ips: list[str] = ['127.0.0.1']
for i in range(num_combos):
    external_alt_ips.append(f'172.20.0.{i+1}')

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
