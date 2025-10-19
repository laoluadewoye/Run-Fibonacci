from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from cryptography import x509
from cryptography.x509.oid import NameOID
from datetime import datetime, timedelta, timezone
from ipaddress import ip_address
from pathlib import Path


def create_key_cert(subject: x509.Name, san_names: list[str], san_ips: list[str], cert_days: int, public_exponent: int,
                    key_length: int, issuer_key=None, issuer_cert=None, is_ca: bool = False,
                    is_key_encrypter: bool = False, is_cert_signer: bool = False) -> tuple:
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
            x509.ExtendedKeyUsage([x509.ExtendedKeyUsageOID.CLIENT_AUTH, x509.ExtendedKeyUsageOID.SERVER_AUTH, ]),
            critical=False
        )
        cert = cert.add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_subject_key_identifier(
                issuer_cert.extensions.get_extension_for_class(x509.SubjectKeyIdentifier).value
            ),
            critical=False
        )

    # Sign and return items
    if is_ca:
        cert = cert.sign(key, hashes.SHA512())
    else:
        cert = cert.sign(issuer_key, hashes.SHA512())

    return key, cert


# Get base folder
BASE_FOLDER = Path(__file__).resolve().parent

# Generate CA TLS materials
print('Creating CA TLS materials...')
ca_cert_name: str = 'ca.test.com'
ca_alt_names: list[str] = ['ca.test.com', 'test.com', 'localhost']
ca_subject: x509.Name = x509.Name([
    x509.NameAttribute(NameOID.COUNTRY_NAME, 'US'),
    x509.NameAttribute(NameOID.COMMON_NAME, ca_cert_name),
])
ca_key, ca_cert = create_key_cert(
    subject=ca_subject, san_names=ca_alt_names, san_ips=['127.0.0.1'], cert_days=2, public_exponent=65537, key_length=4096,
    is_ca=True, is_cert_signer=True
)
ca_key_string = ca_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.TraditionalOpenSSL,
    encryption_algorithm=serialization.NoEncryption()
).decode()
ca_cert_string = ca_cert.public_bytes(serialization.Encoding.PEM).decode()

# Generate external TLS materials
num_combos = len(['rest']) * len(['alma', 'alpine']) * len(['none', 'file'])
external_alt_ips: list[str] = ['127.0.0.1']
for i in range(num_combos):
    external_alt_ips.append(f'172.20.0.{i+1}')

print('Creating external TLS materials...')
external_cert_name: str = 'external.test.com'
external_alt_names: list[str] = [external_cert_name, 'localhost']
external_subject: x509.Name = x509.Name([
    x509.NameAttribute(NameOID.COUNTRY_NAME, 'US'),
    x509.NameAttribute(NameOID.COMMON_NAME, external_cert_name),
])
external_key, external_cert = create_key_cert(
    subject=external_subject, san_names=external_alt_names, san_ips=external_alt_ips, cert_days=1, public_exponent=65537,
    key_length=4096, issuer_key=ca_key, issuer_cert=ca_cert, is_key_encrypter=True
)
external_key_string = external_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.TraditionalOpenSSL,
    encryption_algorithm=serialization.NoEncryption()
).decode()
external_cert_string = external_cert.public_bytes(serialization.Encoding.PEM).decode()

# Save TLS materials for encrypted communication
with open(f'{BASE_FOLDER}/test_self.key', 'w') as external_key_file:
    external_key_file.write(external_key_string)

with open(f'{BASE_FOLDER}/test_self.crt', 'w') as external_cert_file:
    external_cert_file.write(external_cert_string)

with open(f'{BASE_FOLDER}/test_self.pem', 'w') as external_pem_file:
    external_pem_file.write(f'{external_cert_file}\n{external_key_file}')

with open(f'{BASE_FOLDER}/test_ca.key', 'w') as ca_key_file:
    ca_key_file.write(ca_key_string)

with open(f'{BASE_FOLDER}/test_ca.crt', 'w') as ca_cert_file:
    ca_cert_file.write(ca_cert_string)
