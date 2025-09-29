from os.path import exists
from os import mkdir
from subprocess import run


# Constants
USE_CASE_NUM: int = 2


def run_secret_command(secret_label, secret_name, secret_location, general_commands_fp):
    # Run the podman command
    secret_command = [
        'podman', 'secret', 'create', '--replace=true', '--label', secret_label, secret_name, secret_location
    ]
    run(secret_command)

    # Save podman command
    print(f'Saving podman command for secret {secret_name} to txt file...')
    with open(general_commands_fp, 'a') as compose_file:
        compose_file.write('\n')
        compose_file.write(' '.join(secret_command).replace('--', '\n\t--'))


def create_secrets(project_folder, stage, fs, dns, general_commands_fp):
    # Create secret label
    secret_label: str = f'{stage["useCasePrefix"]}={USE_CASE_NUM}'

    # Create CA secrets
    print(f'Defining secret {dns['caName']}-{fs['certExt']}...')
    run_secret_command(
        secret_label,
        f'{dns['caName']}-{fs['certExt']}',
        f'{project_folder}/{fs['tlsFolder']}/{dns['caName']}.{fs['certExt']}',
        general_commands_fp
    )

    # Create server stage secrets
    for i in range(stage['count']):
        server_stage_index = i + 1
        server_stage_name = f'{stage['namePrefix']}-{server_stage_index}'

        print(f'Defining secrets for {server_stage_name}...')
        run_secret_command(
            secret_label,
            f'{server_stage_name}-{fs['keyExt']}',
            f'{project_folder}/{fs['tlsFolder']}/{server_stage_name}.{fs['keyExt']}',
            general_commands_fp
        )
        run_secret_command(
            secret_label,
            f'{server_stage_name}-{fs['certExt']}',
            f'{project_folder}/{fs['tlsFolder']}/{server_stage_name}.{fs['certExt']}',
            general_commands_fp
        )


def create_containers(base_folder, project_folder, setup_config):
    # Create subgroups to save space
    stage = setup_config['stage']
    fs = setup_config['fs']
    dns = setup_config['dns']
    network = setup_config['platform']['network']
    envs = setup_config['envs']

    # Create output folder
    if not exists(f'{base_folder}/{fs['outputFolder']}'):
        mkdir(f'{base_folder}/{fs['outputFolder']}')

    # Create the network
    print('Defining network...')
    network_command = [
        'podman', 'network', 'create', '--label', f'{stage["useCasePrefix"]}={USE_CASE_NUM}',
        '--driver', network['driver'], '--subnet', network['subnet'], '--ip-range', network['range'],
        '--gateway', network['gateway'], network['name']
    ]
    run(network_command)

    # Save command for container file
    print(f'Saving podman command for network {network['name']} to txt file...')
    general_commands_fp = f'{base_folder}/{fs['outputFolder']}/{stage["useCasePrefix"]}-{USE_CASE_NUM}-commands.txt'
    with open(general_commands_fp, 'w') as compose_file:
        compose_file.write(' '.join(network_command).replace('--', '\n\t--'))

    # Create the secrets
    create_secrets(project_folder, stage, fs, dns, general_commands_fp)

    # Create a list of host mappings
    print('Defining host mappings...')
    server_stage_mappings = [
        f'{stage['namePrefix']}-{i + 1}.{setup_config['dns']['domain']}:{network['prefix']}.{network['startAddress'] + i + 1}'
        for i in range(stage['count'])
    ]

    # Create the containers
    for i in range(stage['count']):
        # Create server stage information
        server_stage_index = i + 1
        server_stage_name = f'{stage['namePrefix']}-{server_stage_index}'
        server_stage_ip_addr: str = f'{network['prefix']}.{network['startAddress'] + server_stage_index}'
        server_stage_hostname: str = f'{stage['namePrefix']}-{server_stage_index}.{setup_config['dns']['domain']}'

        # Create the destination hostname
        if server_stage_index < stage['count']:
            dest_stage_hostname: str = f'{stage['namePrefix']}-{server_stage_index + 1}.{setup_config['dns']['domain']}'
        elif server_stage_index == stage['count']:
            dest_stage_hostname: str = f'{stage['namePrefix']}-1.{setup_config['dns']['domain']}'
        else:
            raise IndexError(f'{server_stage_index} is invalid.')

        # Start the command creation
        print(f'Creating command script for container {server_stage_name}...')
        container_command = ['podman', 'run', '--detach', '--network', network['name'], f'--ip={server_stage_ip_addr}']

        # Add a label
        container_command.extend([
            '--label', f'{stage["useCasePrefix"]}={USE_CASE_NUM}'
        ])

        # Add a binding port if the first container
        if server_stage_index == 1:
            print(f'Defining port binding for container {server_stage_name}...')
            container_command.extend([
                '--publish', f'{setup_config['platform']['startPort']}:{setup_config['platform']['startPort']}'
            ])

        # Add secrets
        print(f'Defining secrets for container {server_stage_name}...')
        container_command.extend([
            '--secret', f'{server_stage_name}-{fs['keyExt']},target={envs['selfKeyTarget']}',
            '--secret', f'{server_stage_name}-{fs['certExt']},target={envs['selfCertTarget']}',
            '--secret', f'{setup_config['dns']['caName']}-{fs['certExt']},target={envs['caCertTarget']}'
        ])

        # Add environmental variables
        print(f'Defining environmental variables for container {server_stage_name}...')
        container_command.extend([
            '--env', f'SERVER_STAGE_COUNT={stage['count']}',
            '--env', f'SERVER_STAGE_INDEX={server_stage_index}',
            '--env', f'SELF_ADDRESS={server_stage_ip_addr}',
            '--env', f'SELF_PORT={setup_config['platform']['startPort']}',
            '--env', f'SECRET_KEY_TARGET={envs['selfKeyTarget']}',
            '--env', f'SECRET_CERT_TARGET={envs['selfCertTarget']}',
            '--env', f'SECRET_CA_CERT_TARGET={envs['caCertTarget']}',
            '--env', f'DEST_ADDRESS={dest_stage_hostname}',
            '--env', f'DEST_PORT={setup_config['platform']['startPort']}',
            '--env', f'THROTTLE_INTERVAL={envs['throttleInterval']}',
            '--env', f'UPPER_BOUND={envs['upperBound']}'
        ])

        # Add host mappings
        print(f'Defining IP host mappings for container {server_stage_name}...')
        container_command.extend([
           f'--add-host={server_stage_mapping}' for server_stage_mapping in server_stage_mappings
        ])

        # Add healthcheck kill policy
        print(f'Defining health check and kill policy for container {server_stage_name}...')
        container_command.extend([
            f'--health-cmd={setup_config['platform']['healthcheckCMD']}',
            f'--health-on-failure={setup_config['platform']['containerFailPolicy']}'
        ])

        container_command.append(f'--health-on-failure={setup_config['platform']['containerFailPolicy']}')

        # Add container name and hostname
        print(f'Defining name and hostname for container {server_stage_name}...')
        container_command.append(f'--name={server_stage_name}')
        container_command.append(f'--hostname={server_stage_hostname}')

        # Add image to pull
        print(f'Defining image for container {server_stage_name}...')
        container_command.append(open(f'{project_folder}/{fs['imageVersionFp']}').read())

        # Save command for container file
        print(f'Saving podman command for container {server_stage_name} to txt file...')
        with open(f'{base_folder}/{fs['outputFolder']}/{server_stage_name}-command.txt', "w") as compose_file:
            compose_file.write(' '.join(container_command).replace('--', '\n\t--'))

        # Run the command
        print(f'Running podman command for container {server_stage_name}...')
        run(container_command)
