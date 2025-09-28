from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from cryptography import x509
from cryptography.x509.oid import NameOID
from datetime import datetime, timedelta, timezone


def create_tls_materials(subject, cert_name, cert_days, issuer_key=None,
                         issuer_cert=None, is_ca=False,
                         is_key_encrypter=False, is_cert_signer=False):
    # Create key
    key: RSAPrivateKey = rsa.generate_private_key(
        public_exponent=65537,
        key_size=4096
    )

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
    cert = cert.not_valid_after(
        datetime.now(timezone.utc) + timedelta(days=cert_days)
    )

    # Add extensions
    cert = cert.add_extension(
        x509.SubjectAlternativeName([
            x509.DNSName(cert_name),
            x509.DNSName('localhost'),
            x509.DNSName('0.0.0.0'),
        ]),
        critical=False
    )
    cert = cert.add_extension(
        x509.BasicConstraints(ca=is_ca, path_length=None),
        critical=True
    )
    cert = cert.add_extension(
        x509.KeyUsage(
            digital_signature=True,
            content_commitment=False,
            key_encipherment=is_key_encrypter,
            data_encipherment=False,
            key_agreement=False,
            key_cert_sign=is_cert_signer,
            crl_sign=True,
            encipher_only=False,
            decipher_only=False,
        ),
        critical=True
    )
    cert = cert.add_extension(
        x509.SubjectKeyIdentifier.from_public_key(key.public_key()),
        critical=False
    )

    # Add additional extensions if needed
    if not is_ca:
        cert = cert.add_extension(
            x509.ExtendedKeyUsage([
                x509.ExtendedKeyUsageOID.CLIENT_AUTH,
                x509.ExtendedKeyUsageOID.SERVER_AUTH,
            ]),
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


# Generate CA TLS materials
ca_cert_name: str = 'ca.test.com'
ca_subject = ca_issuer = x509.Name([
    x509.NameAttribute(NameOID.COUNTRY_NAME, 'US'),
    x509.NameAttribute(NameOID.COMMON_NAME, ca_cert_name),
])
ca_key, ca_cert = create_tls_materials(
    ca_subject, ca_cert_name, 2, is_ca=True,
    is_cert_signer=True
)
ca_key_bytes: bytes = ca_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.TraditionalOpenSSL,
    encryption_algorithm=serialization.NoEncryption()
)
ca_cert_bytes: bytes = ca_cert.public_bytes(serialization.Encoding.PEM)

# Generate external TLS materials
external_cert_name: str = 'external.test.com'
external_subject = x509.Name([
    x509.NameAttribute(NameOID.COUNTRY_NAME, 'US'),
    x509.NameAttribute(NameOID.COMMON_NAME, external_cert_name),
])
external_key, external_cert = create_tls_materials(
    external_subject, external_cert_name, 1,
    issuer_key=ca_key, issuer_cert=ca_cert, is_key_encrypter=True
)

# Save TLS materials for external communication
with open('test_self.key', 'w') as key_file:
    key_file.write(
        external_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ).decode()
    )

with open('test_self.crt', 'w') as cert_file:
    cert_file.write(
        external_cert.public_bytes(serialization.Encoding.PEM).decode()
    )

with open('test_ca.key', 'w') as ca_key_file:
    ca_key_file.write(ca_key_bytes.decode())

with open('test_ca.crt', 'w') as ca_cert_file:
    ca_cert_file.write(ca_cert_bytes.decode())
