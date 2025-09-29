from cryptography.hazmat.primitives import serialization
from base64 import b64encode
from subprocess import run

def create_secrets(base_folder, setup_config):
    # Create subgroups to save space
    stage = setup_config['stage']
    out_folder = setup_config['fs']['outputFolder']
    external = setup_config['fs']['external']

    ca_cert_name: str = f'ca.{setup_config['dns']['domain']}'
    server_stage_cert_name: str = f'{stage['namePrefix']}-{0}.{setup_config['dns']['domain']}'

    # Create CA secrets
    print('Creating CA secrets...')
    run([
        'docker', 'secret', 'create', f'{stage['useCasePrefix']}-ca-key',
        f'{base_folder}/{out_folder}/{external['caKeyName']}'
    ])
    run([
        'docker', 'secret', 'create', f'{stage['useCasePrefix']}-ca-cert',
        f'{base_folder}/{out_folder}/{external['caCertName']}'
    ])

    # Create server stage secrets
    for i in range(stage['count']):
        server_stage_index = i + 1
        server_stage_name_prefix = f'{stage['namePrefix']}-{server_stage_index}'

        print(f'Creating server stage {server_stage_index} secrets...')
        run([
            'docker', 'secret', 'create',
            f'{stage['useCasePrefix']}-{stage['namePrefix']}-{server_stage_index}-key',
            f'{base_folder}/{out_folder}/{server_stage_name_prefix}.key'
        ])
        run([
            'docker', 'secret', 'create',
            f'{stage['useCasePrefix']}-{stage['namePrefix']}-{server_stage_index}-cert',
            f'{base_folder}/{out_folder}/{server_stage_name_prefix}.crt'
        ])
