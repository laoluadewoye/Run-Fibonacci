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
    create_chart(BASE_FOLDER, project_folder, setup_config, USE_CASE_NUM)

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

    # Wait for the IP address of the ingress to appear
    print(f'Waiting for {core_name}-ingress to get an IP address...')
    command = (
        "kubectl wait --for=jsonpath={.status.loadBalancer.ingress} " +
        f"ingress/{core_name}-ingress -n {core_name}-namespace --timeout=60s"
    )
    run(command, shell=True)

    # Parse out IP address
    print(f'Obtaining updated {core_name}-ingress information...')
    ingress_info = run(
        ['kubectl', 'get', 'ingress', f'{core_name}-ingress', '-n', f'{core_name}-namespace', '-o', 'json'],
        capture_output=True, text=True
    )

    # Send a get request to the start API
    for i in range(setup_config['stage']['startDelay'], 0, -1):
        print(f'Waiting {i} seconds to start sequence...')
        sleep(1)

    ingress_ip = loads(ingress_info.stdout)['status']['loadBalancer']['ingress'][0]['ip']

    external_key_fp = f'{project_folder}/{fs['tlsFolder']}/{dns['externalName']}.{fs['keyExt']}'
    external_cert_fp = f'{project_folder}/{fs['tlsFolder']}/{dns['externalName']}.{fs['certExt']}'
    external_ca_cert_fp = f'{project_folder}/{fs['tlsFolder']}/{dns['caName']}.{fs['certExt']}'

    response = request(
        method='GET',
        url=f'https://{ingress_ip}/v{USE_CASE_NUM}{dns['startAPI']}',
        headers={"Host": dns['domain']},
        cert=(external_cert_fp, external_key_fp),
        verify=False
        # The above verify command is a current stop measure.
        # The line below is the real parameter setting, but I'm getting self-signed certificate errors.
        # verify=external_ca_cert_fp
    )
    print('Response status code:', response.status_code)
    print('Response contents:', response.json())
    print('To remove the deployment, run the following commands:')
    print(f'\thelm uninstall {release_name}')
    print(f'\tkubectl delete namespace {core_name}-namespace')
    print(f'\tkubectl delete validatingadmissionpolicy {core_name}-admission-policy')
    print(f'\tkubectl delete validatingadmissionpolicybinding {core_name}-admission-policy-binding')
