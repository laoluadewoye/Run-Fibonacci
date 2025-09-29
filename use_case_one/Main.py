from os.path import abspath, dirname, exists
from os import mkdir
from json import loads
from subprocess import run
from time import sleep
from requests import request
from GenerateTLS import create_tls_materials
from GenerateCompose import create_compose


if __name__ == '__main__':
    # Get base folder
    BASE_FOLDER: str = abspath(dirname(__file__))

    # Load configuration
    with open('./setup_config.json') as setup_file:
        setup_config: dict = loads(setup_file.read())

        # Create subgroups to save space
        dns = setup_config['dns']
        fs = setup_config['fs']

    # Create output folder
    if not exists(f'{BASE_FOLDER}/{fs['outputFolder']}'):
        mkdir(f'{BASE_FOLDER}/{fs['outputFolder']}')

    # Create keys and certificates
    create_tls_materials(BASE_FOLDER, setup_config)

    # Create Docker secrets and containers
    create_compose(BASE_FOLDER, setup_config)

    # Run Compose File
    print('Running Docker Compose configuration...')
    run(['docker-compose', '-f', f'{BASE_FOLDER}/docker-compose.json', 'up', '-d'])

    # Send a get request to the start API
    for i in range(setup_config['stage']['startDelay'], 0, -1):
        print(f'Waiting {i} seconds to start sequence...')
        sleep(1)

    starting_ap = dns['default']
    starting_port = setup_config['platform']['port']

    external_key_fp = f'{BASE_FOLDER}/{fs['outputFolder']}/{dns['externalName']}.{fs['keyExt']}'
    external_cert_fp = f'{BASE_FOLDER}/{fs['outputFolder']}/{dns['externalName']}.{fs['certExt']}'
    external_ca_cert_fp = f'{BASE_FOLDER}/{fs['outputFolder']}/{dns['caName']}.{fs['certExt']}'

    response = request(
        method='GET',
        url=f'https://{starting_ap}:{starting_port}/start',
        cert=(external_cert_fp, external_key_fp),
        verify=external_ca_cert_fp
    )
    print('Response status code:', response.status_code)
    print('Response contents:', response.json())
