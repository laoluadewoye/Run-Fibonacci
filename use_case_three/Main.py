from pathlib import Path
from json import loads
from subprocess import run
from time import sleep
from requests import request
from GenerateTLS import create_tls_materials
from GeneratePods import create_chart


if __name__ == '__main__':
    # Constants
    USE_CASE_NUM: int = 3

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
        use_case_prefix = setup_config['stage']['useCasePrefix']

    # Create keys and certificates
    create_tls_materials(project_folder, setup_config)

    # Create Kubernetes Helm chart
    create_chart(BASE_FOLDER, project_folder, setup_config)

    # Create a new Helm release
    core_name = f'{use_case_prefix}-{USE_CASE_NUM}'
    release_name = f'{core_name}-release'

    print(f'Checking helm if {release_name} exists...')
    existing_releases = run(['helm', 'list'], capture_output=True, text=True)
    if release_name in existing_releases.stdout:
        print(f'Deleting {release_name}...')
        run(['helm', 'uninstall', release_name])

        print(f'Deleting namespace and admission policy for {release_name}...')
        run(['kubectl', 'delete', 'namespace', f'{core_name}-namespace'])
        run(['kubectl', 'delete', 'validatingadmissionpolicy', f'{core_name}-admission-policy'])
        run(['kubectl', 'delete', 'validatingadmissionpolicybinding', f'{core_name}-admission-policy-binding'])

    print(f'Creating {release_name}...')
    run(['helm', 'install', release_name, f'{BASE_FOLDER}/{fs['outputFolder']}'])

    # # Send a get request to the start API
    # for i in range(setup_config['stage']['startDelay'], 0, -1):
    #     print(f'Waiting {i} seconds to start sequence...')
    #     sleep(1)
    #
    # starting_ap = dns['default']
    # starting_port = setup_config['platform']['startPort']
    #
    # external_key_fp = f'{project_folder}/{fs['tlsFolder']}/{dns['externalName']}.{fs['keyExt']}'
    # external_cert_fp = f'{project_folder}/{fs['tlsFolder']}/{dns['externalName']}.{fs['certExt']}'
    # external_ca_cert_fp = f'{project_folder}/{fs['tlsFolder']}/{dns['caName']}.{fs['certExt']}'
    #
    # response = request(
    #     method='GET',
    #     url=f'https://{starting_ap}:{starting_port}/start',
    #     cert=(external_cert_fp, external_key_fp),
    #     verify=external_ca_cert_fp
    # )
    # print('Response status code:', response.status_code)
    # print('Response contents:', response.json())
    # print('Run the program RemovePodman.py to remove the containers once done with them.')
