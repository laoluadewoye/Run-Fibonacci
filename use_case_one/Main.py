from pathlib import Path
from json import loads
from subprocess import run
from time import sleep
from requests import request
from GenerateTLS import create_tls_materials
from GenerateCompose import create_compose


if __name__ == '__main__':
    # Get base folder
    BASE_FOLDER = Path(__file__).resolve().parent

    # Get project folder
    project_folder = Path(BASE_FOLDER).resolve().parent

    # Load configuration from the project folder
    with open(f'{project_folder}/setup_config.json') as setup_file:
        setup_config: dict = loads(setup_file.read())

        # Create subgroups to save space
        dns = setup_config['dns']
        fs = setup_config['fs']

    # Create keys and certificates
    create_tls_materials(project_folder, setup_config)

    # Create Docker secrets and containers
    create_compose(BASE_FOLDER, project_folder, setup_config)

    # Run Compose File
    compose_file = f'{BASE_FOLDER}/{fs['outputFolder']}/{fs['composeOutput']}'

    print('Running Docker Compose configuration...')
    run(['docker', 'compose', '-f', compose_file, 'up', '-d'])

    # Send a get request to the start API
    for i in range(setup_config['stage']['startDelay'], 0, -1):
        print(f'Waiting {i} seconds to start sequence...')
        sleep(1)

    starting_ap = dns['default']
    starting_port = setup_config['platform']['startPort']

    external_key_fp = f'{project_folder}/{fs['tlsFolder']}/{dns['externalName']}.{fs['keyExt']}'
    external_cert_fp = f'{project_folder}/{fs['tlsFolder']}/{dns['externalName']}.{fs['certExt']}'
    external_ca_cert_fp = f'{project_folder}/{fs['tlsFolder']}/{dns['caName']}.{fs['certExt']}'

    response = request(
        method='GET',
        url=f'https://{starting_ap}:{starting_port}{dns['startAPI']}',
        cert=(external_cert_fp, external_key_fp),
        verify=external_ca_cert_fp
    )
    print('Response status code:', response.status_code)
    print('Response contents:', response.json())
    print(f'Use the command "docker compose -f {compose_file} rm --stop --force" to remove the containers once done with them.')
