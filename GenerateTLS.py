from os.path import exists
from os import mkdir
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from cryptography import x509
from cryptography.x509.oid import NameOID
from datetime import datetime, timedelta, timezone


def create_key_cert(subject, alt_names, cert_days, public_exponent, key_length, issuer_key=None,
                    issuer_cert=None, is_ca=False, is_key_encrypter=False, is_cert_signer=False):
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
    cert = cert.add_extension(
        x509.SubjectAlternativeName([x509.DNSName(cert_name) for cert_name in alt_names]),
        critical=False
    )
    cert = cert.add_extension(x509.BasicConstraints(ca=is_ca, path_length=None), critical=True)
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

    # Sign and return items
    if is_ca:
        cert = cert.sign(key, hashes.SHA512())
    else:
        cert = cert.sign(issuer_key, hashes.SHA512())
    
    return key, cert


def create_tls_materials(project_folder, setup_config):
    # Create subgroups to save space
    dns = setup_config['dns']
    tls = setup_config['tls']
    fs = setup_config['fs']
    tls_folder = setup_config['fs']['tlsFolder']
    network = setup_config['platform']['network']
    stage = setup_config['stage']

    # Create TLS folder
    if not exists(f'{project_folder}/{tls_folder}'):
        mkdir(f'{project_folder}/{tls_folder}')

    # Generate CA TLS materials
    print('Creating CA TLS materials...')
    ca_cert_name: str = f'{dns['caName']}.{dns['domain']}'
    ca_alt_names = [ca_cert_name, dns['domain'], dns['default']]
    ca_subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, dns['countryInitials']),
        x509.NameAttribute(NameOID.COMMON_NAME, ca_cert_name),
    ])
    ca_key, ca_cert = create_key_cert(
        subject=ca_subject, alt_names=ca_alt_names, cert_days=tls['cert']['validDaysCA'],
        public_exponent=tls['rsa']['publicExponent'], key_length=tls['rsa']['keyLength'], is_ca=True,
        is_cert_signer=True
    )

    # Generate external TLS materials
    print('Creating external TLS materials...')
    external_cert_name: str = f'{dns['externalName']}.{dns['domain']}'
    external_alt_names = [external_cert_name, dns['domain'], dns['default']]
    external_subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, dns['countryInitials']),
        x509.NameAttribute(NameOID.COMMON_NAME, external_cert_name),
    ])
    external_key, external_cert = create_key_cert(
        subject=external_subject, alt_names=external_alt_names, cert_days=tls['cert']['validDaysLeaf'],
        public_exponent=tls['rsa']['publicExponent'], key_length=tls['rsa']['keyLength'],
        issuer_key=ca_key, issuer_cert=ca_cert, is_key_encrypter=True
    )

    # Save TLS materials for external communication
    print('Saving external TLS materials...')
    with open(f'{project_folder}/{tls_folder}/{dns['externalName']}.{fs['keyExt']}', 'w') as key_file:
        key_file.write(
            external_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ).decode()
        )

    with open(f'{project_folder}/{tls_folder}/{dns['externalName']}.{fs['certExt']}', 'w') as cert_file:
        cert_file.write(external_cert.public_bytes(serialization.Encoding.PEM).decode())

    print('Saving CA TLS materials...')
    with open(f'{project_folder}/{tls_folder}/{dns['caName']}.{fs['keyExt']}', 'w') as ca_key_file:
        ca_key_file.write(
            ca_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ).decode()
        )

    with open(f'{project_folder}/{tls_folder}/{dns['caName']}.{fs['certExt']}', 'w') as ca_cert_file:
        ca_cert_file.write(ca_cert.public_bytes(serialization.Encoding.PEM).decode())

    # Generate server stage TLS materials
    for i in range(stage['count']):
        server_stage_index = i + 1
        print(f'Creating TLS materials for server stage {server_stage_index}...')

        # Create current server_stage information
        server_stage_cert_name: str = f'{stage['namePrefix']}-{server_stage_index}.{dns['domain']}'
        server_stage_ip_addr: str = f'{network['prefix']}.{network['startAddress'] + server_stage_index}'
        server_stage_alt_names = [
            server_stage_cert_name, server_stage_ip_addr, dns['domain'], dns['default']
        ]
        server_stage_subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, dns['countryInitials']),
            x509.NameAttribute(NameOID.COMMON_NAME, server_stage_cert_name),
        ])
        server_stage_key, server_stage_cert = create_key_cert(
            subject=server_stage_subject, alt_names=server_stage_alt_names, cert_days=tls['cert']['validDaysLeaf'],
            public_exponent=tls['rsa']['publicExponent'], key_length=tls['rsa']['keyLength'],
            issuer_key=ca_key, issuer_cert=ca_cert, is_key_encrypter=True
        )

        # Save server stage TLS information to file
        print(f'Saving TLS materials for server stage {server_stage_index}...')
        server_stage_name_prefix = f'{stage['namePrefix']}-{server_stage_index}'

        with open(f'{project_folder}/{tls_folder}/{server_stage_name_prefix}.{fs['keyExt']}', 'w') as server_stage_key_file:
            server_stage_key_file.write(
                server_stage_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption()
                ).decode()
            )

        with open(f'{project_folder}/{tls_folder}/{server_stage_name_prefix}.{fs['certExt']}', 'w') as server_stage_cert_file:
            server_stage_cert_file.write(server_stage_cert.public_bytes(serialization.Encoding.PEM).decode())
