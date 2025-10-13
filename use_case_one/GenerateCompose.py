from os.path import exists
from os import mkdir
from json import dump
from pathlib import Path


def create_compose(base_folder: Path, project_folder: Path, setup_config: dict, use_case_num: int) -> None:
    # Create subgroups to save space
    network: dict = setup_config['engine']['network']
    dns: dict = setup_config['dns']
    stage: dict = setup_config['stage']
    fs: dict = setup_config['fs']
    envs: dict = setup_config['envs']

    # Create output folder
    if not exists(f'{base_folder}/{fs['outputFolder']}'):
        mkdir(f'{base_folder}/{fs['outputFolder']}')

    # Create start of json config
    compose_name: str = f"{stage['useCasePrefix']}-{use_case_num}-{stage['composeNameSuffix']}"
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
    server_stage_mappings: list[str] = [
        f'{stage['namePrefix']}-{i + 1}.{dns['domain']}={network['prefix']}.{network['startAddress'] + i + 1}'
        for i in range(stage['count'])
    ]

    # Fill in services
    for i in range(stage['count']):
        # Create server stage information
        server_stage_index: int = i + 1
        server_stage_name: str = f'{stage['namePrefix']}-{server_stage_index}'
        server_stage_ip_addr: str = f'{network['prefix']}.{network['startAddress'] + server_stage_index}'
        server_stage_hostname: str = f'{stage['namePrefix']}-{server_stage_index}.{dns['domain']}'

        # Create the destination hostname
        if server_stage_index < stage['count']:
            dest_stage_hostname: str = f'{stage['namePrefix']}-{server_stage_index + 1}.{dns['domain']}'
        elif server_stage_index == stage['count']:
            dest_stage_hostname: str = f'{stage['namePrefix']}-1.{dns['domain']}'
        else:
            raise IndexError(f'{server_stage_index} is invalid.')

        # Create the service
        print(f'Defining service {server_stage_name}...')
        compose_json['services'][server_stage_name] = {
            'hostname': server_stage_hostname,
            'extra_hosts': server_stage_mappings,
            'image': open(f'{project_folder}/{fs['imageVersionFp']}').read(),
            'restart': setup_config['engine']['containerRestartPolicy'],
            'environment': {
                'SERVER_STAGE_COUNT': stage['count'],
                'SERVER_STAGE_INDEX': server_stage_index,
                'SELF_LISTENING_ADDRESS': server_stage_ip_addr,
                'SELF_HEALTHCHECK_ADDRESS': server_stage_ip_addr,
                'SELF_PORT': setup_config['engine']['startPort'],
                'SECRET_KEY_TARGET': f'{envs['tlsTarget']}/{envs['selfName']}.{fs['keyExt']}',
                'SECRET_CERT_TARGET': f'{envs['tlsTarget']}/{envs['selfName']}.{fs['certExt']}',
                'SECRET_CA_CERT_TARGET': f'{envs['tlsTarget']}/{dns['caName']}.{fs['certExt']}',
                'DEST_ADDRESS': dest_stage_hostname,
                'DEST_PORT': setup_config['engine']['startPort'],
                'THROTTLE_INTERVAL': envs['throttleInterval'],
                'UPPER_BOUND': envs['upperBound']
            },
            'secrets': [
                {
                    'source': f'{server_stage_name}-{fs['keyExt']}',
                    'target': f'{envs['tlsTarget']}/{envs['selfName']}.{fs['keyExt']}'
                },
                {
                    'source': f'{server_stage_name}-{fs['certExt']}',
                    'target': f'{envs['tlsTarget']}/{envs['selfName']}.{fs['certExt']}'
                },
                {
                    'source': f'{dns['caName']}-{fs['certExt']}',
                    'target': f'{envs['tlsTarget']}/{dns['caName']}.{fs['certExt']}'
                },
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
                f'{setup_config['engine']['startPort']}:{setup_config['engine']['startPort']}'
            ]

    # Fill in secrets
    print(f'Defining secret {dns['caName']}-{fs['certExt']}...')
    compose_json['secrets'][f'{dns['caName']}-{fs['certExt']}'] = {
        'file': f'{project_folder}/{fs['tlsFolder']}/{dns['caName']}.{fs['certExt']}'
    }
    for i in range(stage['count']):
        server_stage_index: int = i + 1
        server_stage_name: str = f'{stage['namePrefix']}-{server_stage_index}'
        print(f'Defining secrets for {server_stage_name}...')

        compose_json['secrets'][f'{server_stage_name}-{fs['keyExt']}'] = {
            'file': f'{project_folder}/{fs['tlsFolder']}/{server_stage_name}.{fs['keyExt']}'
        }
        compose_json['secrets'][f'{server_stage_name}-{fs['certExt']}'] = {
            'file': f'{project_folder}/{fs['tlsFolder']}/{server_stage_name}.{fs['certExt']}'
        }

    # Save json file
    print('Saving compose definitions to json file...')
    with open(f'{base_folder}/{fs['outputFolder']}/{fs['composeOutput']}', 'w') as compose_file:
        dump(compose_json, compose_file, indent=4)
