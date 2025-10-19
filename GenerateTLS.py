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
    key_str = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()
    ).decode()
    cert_str = cert.public_bytes(serialization.Encoding.PEM).decode()

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


def create_tls_materials(project_folder: Path, setup_config: dict) -> None:
    # Create subgroups to save space
    dns: dict = setup_config['dns']
    tls: dict = setup_config['tls']
    fs: dict = setup_config['fs']
    tls_folder: dict = setup_config['fs']['tlsFolder']
    network: dict = setup_config['engine']['network']
    stage: dict = setup_config['stage']

    # Create TLS folder
    if exists(f'{project_folder}/{tls_folder}'):
        rmtree(f'{project_folder}/{tls_folder}')
    mkdir(f'{project_folder}/{tls_folder}')

    # Generate CA TLS materials
    print('Creating CA TLS materials...')
    ca_cert_name: str = f'{dns['caName']}.{dns['domain']}'
    ca_alt_names: list[str] = [ca_cert_name, dns['domain'], dns['default']]
    ca_ips: list[str] = [f'{network['prefix']}.{network['startAddress']}']
    ca_subject: x509.Name = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, dns['countryInitials']),
        x509.NameAttribute(NameOID.COMMON_NAME, ca_cert_name),
    ])
    ca_key, ca_cert = create_key_cert(
        subject=ca_subject, san_names=ca_alt_names, san_ips=ca_ips, cert_days=tls['cert']['validDaysCA'],
        public_exponent=tls['rsa']['publicExponent'], key_length=tls['rsa']['keyLength'],
        filename=f'{project_folder}/{tls_folder}/{dns['caName']}', key_ext=fs['keyExt'], cert_ext=fs['certExt'],
        pem_ext=fs['pemExt'], is_ca=True, is_cert_signer=True
    )

    # Generate ingress TLS materials
    print('Creating ingress TLS materials...')
    ingress_alt_names: list[str] = [
        dns['domain'], dns['default'], f'v3.{dns['domain']}', f'v4.{dns['domain']}',
        f'{dns['ingressName']}.{dns['domain']}'
    ]
    ingress_subject: x509.Name = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, 'US'),
        x509.NameAttribute(NameOID.COMMON_NAME, dns['domain']),
    ])
    create_key_cert(
        subject=ingress_subject, san_names=ingress_alt_names, san_ips=[dns['defaultIP']],
        cert_days=tls['cert']['validDaysLeaf'], public_exponent=tls['rsa']['publicExponent'],
        key_length=tls['rsa']['keyLength'], filename=f'{project_folder}/{tls_folder}/{dns['ingressName']}',
        key_ext=fs['keyExt'], cert_ext=fs['certExt'],  pem_ext=fs['pemExt'], issuer_key=ca_key, issuer_cert=ca_cert,
        ca_suffix=dns['caName'], is_key_encrypter=True
    )

    # Generate external TLS materials
    print('Creating external TLS materials...')
    external_cert_name: str = f'{dns['externalName']}.{dns['domain']}'
    external_alt_names: list[str] = [external_cert_name, dns['domain'], dns['default']]
    external_subject: x509.Name = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, dns['countryInitials']),
        x509.NameAttribute(NameOID.COMMON_NAME, external_cert_name),
    ])
    create_key_cert(
        subject=external_subject, san_names=external_alt_names, san_ips=[dns['defaultIP']],
        cert_days=tls['cert']['validDaysLeaf'], public_exponent=tls['rsa']['publicExponent'],
        key_length=tls['rsa']['keyLength'], filename=f'{project_folder}/{tls_folder}/{dns['externalName']}',
        key_ext=fs['keyExt'], cert_ext=fs['certExt'], pem_ext=fs['pemExt'], issuer_key=ca_key, issuer_cert=ca_cert,
        ca_suffix=dns['caName'], is_key_encrypter=True
    )

    # Generate datastore TLS materials
    print('Creating datastore TLS materials...')
    datastore_cert_name: str = f'{dns['datastoreName']}.{dns['domain']}'
    datastore_alt_names: list[str] = [datastore_cert_name, dns['domain'], dns['default']]
    datastore_ip_addr: list[str] = [setup_config['server']['datastore']['networkAddress']]
    datastore_subject: x509.Name = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, dns['countryInitials']),
        x509.NameAttribute(NameOID.COMMON_NAME, datastore_cert_name),
    ])
    create_key_cert(
        subject=datastore_subject, san_names=datastore_alt_names, san_ips=datastore_ip_addr,
        cert_days=tls['cert']['validDaysLeaf'], public_exponent=tls['rsa']['publicExponent'],
        key_length=tls['rsa']['keyLength'], filename=f'{project_folder}/{tls_folder}/{dns['datastoreName']}',
        key_ext=fs['keyExt'], cert_ext=fs['certExt'], pem_ext=fs['pemExt'], issuer_key=ca_key, issuer_cert=ca_cert,
        ca_suffix=dns['caName'], is_key_encrypter=True
    )

    # Generate server stage TLS materials
    for i in range(stage['count']):
        server_stage_index = i + 1
        print(f'Creating TLS materials for server stage {server_stage_index}...')

        # Create current server_stage information
        server_stage_cert_name: str = f'{stage['namePrefix']}-{server_stage_index}.{dns['domain']}'
        server_stage_service_name: str = f'{stage['namePrefix']}-{server_stage_index}-service'
        server_stage_ips: list[str] = [f'{network['prefix']}.{network['startAddress'] + server_stage_index}']
        server_stage_alt_names: list[str] = [
            server_stage_cert_name, server_stage_service_name, dns['domain'], dns['default']
        ]
        server_stage_subject: x509.Name = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, dns['countryInitials']),
            x509.NameAttribute(NameOID.COMMON_NAME, server_stage_cert_name),
        ])
        server_stage_name_prefix: str = f'{stage['namePrefix']}-{server_stage_index}'
        create_key_cert(
            subject=server_stage_subject, san_names=server_stage_alt_names, san_ips=server_stage_ips,
            cert_days=tls['cert']['validDaysLeaf'], public_exponent=tls['rsa']['publicExponent'],
            key_length=tls['rsa']['keyLength'], filename=f'{project_folder}/{tls_folder}/{server_stage_name_prefix}',
            key_ext=fs['keyExt'], cert_ext=fs['certExt'], pem_ext=fs['pemExt'], issuer_key=ca_key, issuer_cert=ca_cert,
            ca_suffix=dns['caName'], is_key_encrypter=True
        )
