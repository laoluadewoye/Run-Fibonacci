from pathlib import Path
import os
from subprocess import run, CompletedProcess
from glob import glob
from itertools import product
from time import sleep
from requests import request, Response

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

# Run the test containers
platforms: list[str] = [dockerfile.split('\\')[-1].split('.')[0] for dockerfile in glob(f'{IMAGE_FOLDER}/*Dockerfile')]
apis: list[str] = ['rest']
test_combos = product(platforms, apis)
start_port: int = 8080
test_index: int = 0
for platform, api in test_combos:
    # Increment index
    test_index += 1
    test_port: int = start_port + test_index

    # Run test
    print(f'Testing fibonacci server running on the {platform.title()} platform using {api} API...')
    run([
        command, 'run', '-d', '-p', f'{test_port}:{test_port}',
        '-v', f'{BASE_FOLDER}/test_self.key:/run/secrets/self.key',
        '-v', f'{BASE_FOLDER}/test_self.crt:/run/secrets/self.crt',
        '-v', f'{BASE_FOLDER}/test_ca.crt:/run/secrets/ca.crt',
        '-e', f'SERVER_API={api}',
        '-e', 'SERVER_STAGE_COUNT=1',
        '-e', 'SERVER_STAGE_INDEX=1',
        '-e', 'SELF_LISTENING_ADDRESS=0.0.0.0',
        '-e', 'SELF_HEALTHCHECK_ADDRESS=localhost',
        '-e', f'SELF_PORT={test_port}',
        '-e', 'SECRET_KEY_TARGET=/run/secrets/self.key',
        '-e', 'SECRET_CERT_TARGET=/run/secrets/self.crt',
        '-e', 'SECRET_CA_CERT_TARGET=/run/secrets/ca.crt',
        '-e', 'DEST_ADDRESS=localhost',
        '-e', f'DEST_PORT={test_port}',
        '-e', 'THROTTLE_INTERVAL=5',
        '-e', 'UPPER_BOUND=4000000000',
        '--name', f'test-fib-{platform}-{api}-container',
        f'{latest_image}-{platform}'
    ])

    # Wait for container to spin up
    for i in range(5, 0, -1):
        print(f'Waiting {i} seconds for container to spin up...')
        sleep(1)

    # Send message
    response: Response = request(
        method='GET',
        url='https://localhost:8081/start',
        cert=(f'{BASE_FOLDER}/test_self.crt', f'{BASE_FOLDER}/test_self.key'),
        verify=f'{BASE_FOLDER}/test_ca.crt'
    )
    print('Response status code:', response.status_code)
    print('Response contents:', response.json())

print("Done. Use your container engine to stop and delete the container whenever you're done.")
