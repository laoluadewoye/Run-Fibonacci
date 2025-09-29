from os.path import exists
from os import mkdir
from json import dump


def create_compose(base_folder, project_folder, setup_config):
    # Create subgroups to save space
    network = setup_config['platform']['network']
    stage = setup_config['stage']
    fs = setup_config['fs']
    envs = setup_config['envs']

    # Create output folder
    if not exists(f'{base_folder}/{fs['outputFolder']}'):
        mkdir(f'{base_folder}/{fs['outputFolder']}')

    # Create start of json config
    compose_name = f"{stage['useCasePrefix']}-1-{stage['composeNameSuffix']}"
    compose_json: dict = {
        'name': compose_name,
        'services': {},
        'networks': {
            network['name']: {
                'name': network['name'],
                'driver': network['driver'],
                'ipam': {
                    'config': [{
                        'subnet': network['subnet'],
                        'ip_range': network['range'],
                        'gateway': network['gateway'],
                    }]
                }
            }
        },
        'secrets': {},
    }

    # Create a list of host mappings
    print('Defining host mappings...')
    server_stage_mappings = [
        f'{stage['namePrefix']}-{i + 1}.{setup_config['dns']['domain']}={network['prefix']}.{network['startAddress'] + i + 1}'
        for i in range(stage['count'])
    ]

    # Fill in services
    for i in range(stage['count']):
        server_stage_index = i + 1
        server_stage_name = f'{stage['namePrefix']}-{server_stage_index}'
        server_stage_ip_addr: str = f'{network['prefix']}.{network['startAddress'] + server_stage_index}'
        server_stage_hostname: str = f'{stage['namePrefix']}-{server_stage_index}.{setup_config['dns']['domain']}'

        print(f'Defining service {server_stage_name}...')

        if server_stage_index < stage['count']:
            dest_stage_hostname: str = f'{stage['namePrefix']}-{server_stage_index + 1}.{setup_config['dns']['domain']}'
        elif server_stage_index == stage['count']:
            dest_stage_hostname: str = f'{stage['namePrefix']}-1.{setup_config['dns']['domain']}'
        else:
            raise IndexError(f'{server_stage_index} is invalid.')

        compose_json['services'][server_stage_name] = {
            'hostname': server_stage_hostname,
            'extra_hosts': server_stage_mappings,
            'image': open(f'{project_folder}/{fs['imageVersionFp']}').read(),
            'restart': setup_config['platform']['restartPolicy'],
            'environment': {
                'SERVER_STAGE_COUNT': stage['count'],
                'SERVER_STAGE_INDEX': server_stage_index,
                'SELF_ADDRESS': server_stage_ip_addr,
                'SELF_PORT': setup_config['platform']['startPort'],
                'SECRET_KEY_TARGET': envs['selfKeyTarget'],
                'SECRET_CERT_TARGET': envs['selfCertTarget'],
                'SECRET_CA_CERT_TARGET': envs['caCertTarget'],
                'DEST_ADDRESS': dest_stage_hostname,
                'DEST_PORT': setup_config['platform']['startPort'],
                'THROTTLE_INTERVAL': envs['throttleInterval'],
                'UPPER_BOUND': envs['upperBound'],
            },
            'secrets': [
                {'source': f'{server_stage_name}-{fs['keyExt']}', 'target': envs['selfKeyTarget']},
                {'source': f'{server_stage_name}-{fs['certExt']}', 'target': envs['selfCertTarget']},
                {'source': f'{setup_config['dns']['caName']}-{fs['certExt']}', 'target': envs['caCertTarget']},
            ],
            'networks': {
                network['name']: {
                    'ipv4_address': server_stage_ip_addr
                }
            }
        }

        # Add port binding if the first service
        if server_stage_index == 1:
            print(f'Defining port binding for service {server_stage_name}...')
            compose_json['services'][server_stage_name]['ports'] = [
                f'{setup_config['platform']['startPort']}:{setup_config['platform']['startPort']}'
            ]

    # Fill in secrets
    print(f'Defining secret {setup_config['dns']['caName']}-{fs['certExt']}...')
    compose_json['secrets'][f'{setup_config['dns']['caName']}-{fs['certExt']}'] = {
        'file': f'{project_folder}/{fs['tlsFolder']}/{setup_config['dns']['caName']}.{fs['certExt']}'
    }
    for i in range(stage['count']):
        server_stage_index = i + 1
        server_stage_name = f'{stage['namePrefix']}-{server_stage_index}'
        print(f'Defining secrets for {server_stage_name}...')

        compose_json['secrets'][f'{server_stage_name}-{fs['keyExt']}'] = {
            'file': f'{project_folder}/{fs['tlsFolder']}/{server_stage_name}.{fs['keyExt']}'
        }
        compose_json['secrets'][f'{server_stage_name}-{fs['certExt']}'] = {
            'file': f'{project_folder}/{fs['tlsFolder']}/{server_stage_name}.{fs['certExt']}'
        }

    # Save json file
    print('Saving compose definitions to json file...')
    with open(f'{base_folder}/{fs['outputFolder']}/docker-compose.json', "w") as compose_file:
        dump(compose_json, compose_file, indent=4)
