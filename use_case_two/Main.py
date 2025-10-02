from pathlib import Path
from json import loads
from time import sleep
from requests import request, Response
from GenerateTLS import create_tls_materials
from GeneratePodman import create_containers


if __name__ == '__main__':
    # Constants
    USE_CASE_NUM: int = 2

    # Get base folder
    BASE_FOLDER: Path = Path(__file__).resolve().parent

    # Get project folder
    project_folder: Path = Path(BASE_FOLDER).resolve().parent

    # Load configuration from the project folder
    with open(f'{project_folder}/setup_config.json') as setup_file:
        setup_config: dict = loads(setup_file.read())

        # Create subgroups to save space
        dns: dict = setup_config['dns']
        fs: dict = setup_config['fs']

    # Create keys and certificates
    create_tls_materials(project_folder, setup_config)

    # Create Podman secrets and containers
    create_containers(BASE_FOLDER, project_folder, setup_config, USE_CASE_NUM)

    # Send a get request to the start API
    for i in range(setup_config['stage']['startDelay'], 0, -1):
        print(f'Waiting {i} seconds to start sequence...')
        sleep(1)

    starting_port: int = setup_config['platform']['startPort']

    external_key_fp: str = f'{project_folder}/{fs['tlsFolder']}/{dns['externalName']}.{fs['keyExt']}'
    external_cert_fp: str = f'{project_folder}/{fs['tlsFolder']}/{dns['externalName']}.{fs['certExt']}'
    external_ca_cert_fp: str = f'{project_folder}/{fs['tlsFolder']}/{dns['caName']}.{fs['certExt']}'

    response: Response = request(
        method='GET',
        url=f'https://{dns['default']}:{starting_port}{dns['startAPI']}',
        cert=(external_cert_fp, external_key_fp),
        verify=external_ca_cert_fp
    )
    print('Response status code:', response.status_code)
    print('Response contents:', response.json())
    print('Run the program RemovePodman.py to remove the containers once done with them.')
