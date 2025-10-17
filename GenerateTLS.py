from shutil import rmtree
from os.path import exists
from os import mkdir
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from cryptography import x509
from cryptography.x509.oid import NameOID
from datetime import datetime, timedelta, timezone
from ipaddress import ip_address
from pathlib import Path


def create_key_cert(subject: x509.Name, san_names: list[str], san_ip: str, cert_days: int, public_exponent: int,
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
    sans = [x509.DNSName(san_name) for san_name in san_names]
    sans.append(x509.IPAddress(ip_address(san_ip)))
    cert = cert.add_extension(x509.SubjectAlternativeName(sans), critical=False)
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

    # Sign and return items
    if is_ca:
        cert = cert.sign(key, hashes.SHA512())
    else:
        cert = cert.sign(issuer_key, hashes.SHA512())
    
    return key, cert


def create_tls_materials(project_folder: Path, setup_config: dict) -> None:
    # Create subgroups to save space
    dns: dict = setup_config['dns']
    tls: dict = setup_config['tls']
    fs: dict = setup_config['fs']
    tls_folder: dict = setup_config['fs']['tlsFolder']
    network: dict = setup_config['platform']['network']
    stage: dict = setup_config['stage']

    # Create TLS folder
    if exists(f'{project_folder}/{tls_folder}'):
        rmtree(f'{project_folder}/{tls_folder}')
    mkdir(f'{project_folder}/{tls_folder}')

    # Generate CA TLS materials
    print('Creating CA TLS materials...')
    ca_cert_name: str = f'{dns['caName']}.{dns['domain']}'
    ca_alt_names: list[str] = [ca_cert_name, dns['domain'], dns['default']]
    ca_ip_addr: str = f'{network['prefix']}.{network['startAddress']}'
    ca_subject: x509.Name = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, dns['countryInitials']),
        x509.NameAttribute(NameOID.COMMON_NAME, ca_cert_name),
    ])
    ca_key, ca_cert = create_key_cert(
        subject=ca_subject, san_names=ca_alt_names, san_ip=ca_ip_addr, cert_days=tls['cert']['validDaysCA'],
        public_exponent=tls['rsa']['publicExponent'], key_length=tls['rsa']['keyLength'], is_ca=True,
        is_cert_signer=True
    )

    # Generate ingress TLS materials
    print('Creating ingress TLS materials...')
    ingress_alt_names: list[str] = [dns['domain'], dns['default'], f'v3.{dns['domain']}', f'v4.{dns['domain']}']
    ingress_subject: x509.Name = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, 'US'),
        x509.NameAttribute(NameOID.COMMON_NAME, dns['domain']),
    ])
    ingress_key, ingress_cert = create_key_cert(
        subject=ingress_subject, san_names=ingress_alt_names, san_ip=dns['defaultIP'],
        cert_days=tls['cert']['validDaysLeaf'], public_exponent=tls['rsa']['publicExponent'],
        key_length=tls['rsa']['keyLength'], issuer_key=ca_key, issuer_cert=ca_cert, is_key_encrypter=True
    )

    # Generate external TLS materials
    print('Creating external TLS materials...')
    external_cert_name: str = f'{dns['externalName']}.{dns['domain']}'
    external_alt_names: list[str] = [external_cert_name, dns['domain'], dns['default']]
    external_subject: x509.Name = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, dns['countryInitials']),
        x509.NameAttribute(NameOID.COMMON_NAME, external_cert_name),
    ])
    external_key, external_cert = create_key_cert(
        subject=external_subject, san_names=external_alt_names, san_ip=dns['defaultIP'],
        cert_days=tls['cert']['validDaysLeaf'], public_exponent=tls['rsa']['publicExponent'],
        key_length=tls['rsa']['keyLength'], issuer_key=ca_key, issuer_cert=ca_cert, is_key_encrypter=True
    )

    # Generate datastore TLS materials
    print('Creating datastore TLS materials...')
    datastore_cert_name: str = f'{dns['datastoreName']}.{dns['domain']}'
    datastore_alt_names: list[str] = [datastore_cert_name, dns['domain'], dns['default']]
    datastore_ip_addr: str = setup_config['server']['datastore']['networkAddress']
    datastore_subject: x509.Name = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, dns['countryInitials']),
        x509.NameAttribute(NameOID.COMMON_NAME, datastore_cert_name),
    ])
    datastore_key, datastore_cert = create_key_cert(
        subject=datastore_subject, san_names=datastore_alt_names, san_ip=datastore_ip_addr,
        cert_days=tls['cert']['validDaysLeaf'], public_exponent=tls['rsa']['publicExponent'],
        key_length=tls['rsa']['keyLength'], issuer_key=ca_key, issuer_cert=ca_cert, is_key_encrypter=True
    )

    # Save TLS materials for CA, ingress, external, and datastore
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

    print('Saving ingress TLS materials...')
    with open(f'{project_folder}/{tls_folder}/{dns['ingressName']}.{fs['keyExt']}', 'w') as ingress_key_file:
        ingress_key_file.write(
            ingress_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ).decode()
        )

    with open(f'{project_folder}/{tls_folder}/{dns['ingressName']}.{fs['certExt']}', 'w') as ingress_cert_file:
        ingress_combined_certs = (f'{ingress_cert.public_bytes(serialization.Encoding.PEM).decode()}'
                                  f'{ca_cert.public_bytes(serialization.Encoding.PEM).decode()}')
        ingress_cert_file.write(ingress_combined_certs)

    print('Saving external TLS materials...')
    with open(f'{project_folder}/{tls_folder}/{dns['externalName']}.{fs['keyExt']}', 'w') as external_key_file:
        external_key_file.write(
            external_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ).decode()
        )

    with open(f'{project_folder}/{tls_folder}/{dns['externalName']}.{fs['certExt']}', 'w') as external_cert_file:
        external_cert_file.write(external_cert.public_bytes(serialization.Encoding.PEM).decode())

    print('Saving datastore TLS materials...')
    with open(f'{project_folder}/{tls_folder}/{dns['datastoreName']}.{fs['keyExt']}', 'w') as datastore_key_file:
        datastore_key_file.write(
            datastore_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ).decode()
        )

    with open(f'{project_folder}/{tls_folder}/{dns['datastoreName']}.{fs['certExt']}', 'w') as datastore_cert_file:
        datastore_cert_file.write(datastore_cert.public_bytes(serialization.Encoding.PEM).decode())

    # Generate server stage TLS materials
    for i in range(stage['count']):
        server_stage_index = i + 1
        print(f'Creating TLS materials for server stage {server_stage_index}...')

        # Create current server_stage information
        server_stage_cert_name: str = f'{stage['namePrefix']}-{server_stage_index}.{dns['domain']}'
        server_stage_service_name: str = f'{stage['namePrefix']}-{server_stage_index}-service'
        server_stage_ip_addr: str = f'{network['prefix']}.{network['startAddress'] + server_stage_index}'
        server_stage_alt_names: list[str] = [
            server_stage_cert_name, server_stage_service_name, dns['domain'], dns['default']
        ]
        server_stage_subject: x509.Name = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, dns['countryInitials']),
            x509.NameAttribute(NameOID.COMMON_NAME, server_stage_cert_name),
        ])
        server_stage_key, server_stage_cert = create_key_cert(
            subject=server_stage_subject, san_names=server_stage_alt_names, san_ip=server_stage_ip_addr,
            cert_days=tls['cert']['validDaysLeaf'], public_exponent=tls['rsa']['publicExponent'],
            key_length=tls['rsa']['keyLength'], issuer_key=ca_key, issuer_cert=ca_cert, is_key_encrypter=True
        )

        # Save server stage TLS information to file
        print(f'Saving TLS materials for server stage {server_stage_index}...')
        server_stage_name_prefix: str = f'{stage['namePrefix']}-{server_stage_index}'

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
