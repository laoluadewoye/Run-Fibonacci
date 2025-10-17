from pathlib import Path
import os
from subprocess import run, CompletedProcess
from itertools import product
from time import sleep
from requests import request, Response


def create_server(folder: Path, server_network: str, server_ip: str, server_port: int, server_image: str,
                  server_platform: str, server_api: str, server_datastore: str, server_datastore_addr: str,
                  server_datastore_port: int, server_name: str) -> None:
    run([
        command, 'run', '-d', '-p', f'{server_port}:{server_port}',
        f'--network={server_network}', f'--ip={server_ip}',
        '-v', f'{folder}/test_self.key:/run/secrets/self.key',
        '-v', f'{folder}/test_self.crt:/run/secrets/self.crt',
        '-v', f'{folder}/test_ca.crt:/run/secrets/ca.crt',
        '-e', f'SERVER_API={server_api}',
        '-e', f'SERVER_DATASTORE={server_datastore}',
        '-e', 'SERVER_STAGE_COUNT=1',
        '-e', 'SERVER_STAGE_INDEX=1',
        '-e', 'SELF_LISTENING_ADDRESS=0.0.0.0',
        '-e', 'SELF_HEALTHCHECK_ADDRESS=localhost',
        '-e', f'SELF_PORT={server_port}',
        '-e', 'SECRET_KEY_TARGET=/run/secrets/self.key',
        '-e', 'SECRET_CERT_TARGET=/run/secrets/self.crt',
        '-e', 'SECRET_CA_CERT_TARGET=/run/secrets/ca.crt',
        '-e', 'DEST_ADDRESS=localhost',
        '-e', f'DEST_PORT={server_port}',
        '-e', f'DATASTORE_ADDRESS={server_datastore_addr}',
        '-e', f'DATASTORE_PORT={server_datastore_port}',
        '-e', 'DATASTORE_FILEPATH=/tmp/datastore.csv',
        '-e', 'DATASTORE_DEFAULT_FILEPATH=/tmp/default.csv',
        '-e', 'DATASTORE_OPERATIONS_FILEPATH=/tmp/operations.csv',
        '-e', 'THROTTLE_INTERVAL=5',
        '-e', 'UPPER_BOUND=4000000000',
        '--name', server_name,
        f'{server_image}-{server_platform}'
    ])

# Create constants
BASE_FOLDER: Path = Path(__file__).resolve().parent
IMAGE_FOLDER: Path = BASE_FOLDER.parent
test_tls_materials: list[str] = ['test_self.key', 'test_self.crt', 'test_ca.key', 'test_ca.crt']

print('Checking for test TLS materials...')
for test_file in test_tls_materials:
    assert os.path.exists(f'{BASE_FOLDER}/{test_file}'), f'{BASE_FOLDER}/{test_file} was not created.'

# Get container image version
latest_image: str = open(f'{IMAGE_FOLDER}/latest_image.adoc').read()
print(f'Creating container using image {latest_image}...')

# Check for a running container
command: str = ''

print('Checking if Docker is installed...')
output: CompletedProcess = run('docker info', capture_output=True, text=True)
if output.stderr == '':
    print('Docker engine is running. Using Docker to run container...')
    command = 'docker'
else:
    print('Docker engine is not running. Trying Podman...')

if command != 'docker':
    output = run('podman info', capture_output=True, text=True)
    if output.stderr == '':
        print('Podman engine is running. Using Podman to run container...')
        command = 'podman'
    else:
        print('Podman engine is not running..')

assert command != '', 'No container engine is running. Please start a container engine.'

# Set up combinations
apis: list[str] = ['rest']
platforms: list[str] = ['alma', 'alpine']
datastores: list[str] = ['none', 'file']

test_combos = product(platforms, datastores)

# Start port settings
cur_ip: int = 1
cur_port: int = 8080

# Create test network
test_fib_net: dict = {}
test_fib_net_name: str = 'test-fib-net'
run([command, 'network', 'create', '--subnet', '172.20.0.0/16', test_fib_net_name])

# Run the test containers
for api in apis:
    datastore_platform: str = 'alpine'

    # Create test datastores
    for datastore in datastores:
        print('------------------------------------------------------------------')
        print('Creating datastore running with the following combination...')
        print(f'Platform: {datastore_platform.title()}')
        print(f'API: {api.upper()}')
        print(f'Datastore: {datastore.title()}')
        datastore_name: str = f'test-fib-{api}-{datastore}-{datastore_platform}-datastore'

        # Check if test datastore already exist and delete if needed
        output = run([command, 'ps' , '-a' , '--filter', f'name={datastore_name}'], capture_output=True, text=True)
        if output.stdout.split('\n')[1] != '':
            run([command, 'stop', datastore_name])
            run([command, 'rm', datastore_name])

        if datastore == 'file': # Create datastore server
            create_server(
                BASE_FOLDER, test_fib_net_name, f'172.20.0.{cur_ip}', cur_port, latest_image,
                datastore_platform, api, 'none', f'localhost', cur_port,
                datastore_name
            )

        # Prepare for next test datastore
        test_fib_net[datastore_name] = {'ip': f'172.20.0.{cur_ip}', 'port': cur_port}
        cur_ip += 1
        cur_port += 1

    # Run combinations
    for platform, datastore in test_combos:
        # Create test server
        print('------------------------------------------------------------------')
        print('Testing fibonacci server running with the following combination...')
        print(f'Platform: {platform.title()}')
        print(f'API: {api.upper()}')
        print(f'Datastore: {datastore.title()}')
        server_name: str = f'test-fib-{api}-{datastore}-{platform}-server'

        # Check if test server already exist and delete if needed
        output = run([command, 'ps', '-a', '--filter', f'name={server_name}'], capture_output=True, text=True)
        if output.stdout.split('\n')[1] != '':
            run([command, 'stop', server_name])
            run([command, 'rm', server_name])

        # Create test server
        datastore_ip: str = test_fib_net[f'test-fib-{api}-{datastore}-{datastore_platform}-datastore']['ip']
        datastore_port: int = test_fib_net[f'test-fib-{api}-{datastore}-{datastore_platform}-datastore']['port']
        create_server(
            BASE_FOLDER, test_fib_net_name, f'172.20.0.{cur_ip}', cur_port, latest_image, platform, api,
            datastore, datastore_ip, datastore_port, server_name
        )

        # Wait for test server to spin up
        for i in range(5, 0, -1):
            print(f'Waiting {i} seconds for container to spin up...')
            sleep(1)

        # Send message to test server
        response: Response = request(
            method='GET',
            url=f'https://localhost:{cur_port}/start',
            cert=(f'{BASE_FOLDER}/test_self.crt', f'{BASE_FOLDER}/test_self.key'),
            verify=f'{BASE_FOLDER}/test_ca.crt'
        )
        print('Response status code:', response.status_code)
        print('Response contents:', response.json())

        # Prepare for next test server
        test_fib_net[server_name] = {'ip': f'172.20.0.{cur_ip}', 'port': cur_port}
        cur_ip += 1
        cur_port += 1

print("Done. Use your container engine to stop and delete the container whenever you're done.")
