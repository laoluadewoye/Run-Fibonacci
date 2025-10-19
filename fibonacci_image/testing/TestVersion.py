from pathlib import Path
from yaml import load as yaml_load, Loader as yaml_loader, dump as yaml_dump
from toml import load as toml_load, dump as toml_dump
from os.path import exists
from subprocess import run, CompletedProcess
from itertools import product
from uuid import uuid4
from time import sleep
from requests import request, Response


def create_server(base_folder: Path, server_network: str, server_ip: str, server_port: int, server_image: str,
                  server_platform: str, server_api: str, server_datastore: str, server_datastore_addr: str,
                  server_datastore_port: int, container_name: str, ds_user: str = '',
                  ds_pass: str = '') -> None:
    # Start command
    create_server_command = [
        command, 'run', '-d', '-p', f'{server_port}:{server_port}',
        f'--network={server_network}', f'--ip={server_ip}',
        '-v', f'{base_folder}/test_self.key:/run/secrets/self.key',
        '-v', f'{base_folder}/test_self.crt:/run/secrets/self.crt',
        '-v', f'{base_folder}/test_ca.crt:/run/secrets/ca.crt',
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
    ]

    # Add username and password if needed
    if ds_user != '' and ds_pass != '':
        create_server_command.extend([
            '-e', f'DATASTORE_USER={ds_user}', '-e', f'DATASTORE_PASSWORD={ds_pass}',
        ])

    # Finish command and run it
    create_server_command.extend(['--name', container_name, f'{server_image}-{server_platform}'])
    run(create_server_command)


def create_elasticstack(base_folder: Path, server_network: str, server_es_info, container_name: str,
                        ds_user: str = '', ds_pass: str = '') -> None:
    pass


def create_mongodb(base_folder: Path, server_network: str, server_ip: str, server_port: int, container_name: str,
                   ds_user: str = '', ds_pass: str = '') -> None:
    # Ingest mongodb configuration
    with open(f'{base_folder}/mongo_datastore.conf') as conf_file:
        mongo_config: dict = yaml_load(conf_file, yaml_loader)

    # Customize socket
    mongo_config['net']['port'] = server_port
    mongo_config['net']['bindIp'] = server_ip

    # Save configuration
    with open(f'{base_folder}/mongo_datastore_custom.conf', 'w') as custom_conf_file:
        custom_conf_file.write(yaml_dump(mongo_config))

    # Run mongodb server
    run([
        command, 'run', '-d', '-p', f'{server_port}:{server_port}',
        f'--network={server_network}', f'--ip={server_ip}',
        '-v', f'{base_folder}/test_self.pem:/run/secrets/self.pem',
        '-v', f'{base_folder}/test_ca.crt:/run/secrets/ca.crt',
        '-v', f'{base_folder}/mongo_datastore_custom.conf:/etc/mongo/mongod.conf',
        '-e', f'MONGO_INITDB_ROOT_USERNAME={ds_user}',
        '-e', f'MONGO_INITDB_ROOT_PASSWORD={ds_pass}',
        '--name', container_name, 'docker.io/library/mongo:8.0.15-noble',
        '--config', '/etc/mongo/mongod.conf'
    ])


def create_postgresql(base_folder: Path, server_network: str, server_ip: str, server_port: int, container_name: str,
                      ds_user: str = '', ds_pass: str = '') -> None:
    # Ingest postgresql configuration
    with open(f'{base_folder}/postgres_datastore.conf') as conf_file:
        postgres_config: dict = toml_load(conf_file)

    # Customize socket
    postgres_config['port'] = server_port
    postgres_config['listen_addresses'] = server_ip

    # Save configuration
    with open(f'{base_folder}/postgres_datastore_custom.conf', 'w') as custom_conf_file:
        toml_dump(postgres_config, custom_conf_file)

    run([
        command, 'run', '-d', '-p', f'{server_port}:{server_port}',
        f'--network={server_network}', f'--ip={server_ip}',
        '-v', f'{base_folder}/test_self.key:/run/secrets/self.key',
        '-v', f'{base_folder}/test_self.crt:/run/secrets/self.crt',
        '-v', f'{base_folder}/test_ca.crt:/run/secrets/ca.crt',
        '-v', f'{base_folder}/postgres_datastore_custom.conf:/etc/postgresql/postgresql.conf',
        '-e', f'POSTGRES_USER={ds_user}',
        '-e', f'POSTGRES_PASSWORD={ds_pass}',
        '--name', container_name, 'docker.io/library/postgres:18.0-alpine3.22',
        '-c', 'config_file=/etc/postgresql/postgresql.conf',
    ])


# Create constants
BASE_FOLDER: Path = Path(__file__).resolve().parent
IMAGE_FOLDER: Path = BASE_FOLDER.parent
test_tls_materials: list[str] = ['test_self.key', 'test_self.crt', 'test_ca.key', 'test_ca.crt']

print('Checking for test TLS materials...')
for test_file in test_tls_materials:
    assert exists(f'{BASE_FOLDER}/{test_file}'), f'{BASE_FOLDER}/{test_file} was not created.'

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

# Create datastore credentials
datastore_user: str = 'test-fib-user'
datastore_password: str = uuid4().hex

# Run the test containers
for api in apis:
    datastore_platform: str = 'alpine'

    # Create test datastores
    for datastore in datastores:
        print('------------------------------------------------------------------')
        print('Creating datastore running with the following combination...')
        print(f'Platform: {datastore_platform.title()} (Only used for file datastore)')
        print(f'API: {api.upper()}')
        print(f'Datastore: {datastore.title()}')
        datastore_name: str = f'test-fib-{api}-{datastore}-datastore'

        # Check if test datastore already exist and delete if needed
        output: CompletedProcess = run([command, 'ps' , '-a' , '--filter', f'name={datastore_name}'], capture_output=True, text=True)
        if output.stdout.split('\n')[1] != '':
            run([command, 'stop', datastore_name])
            run([command, 'rm', datastore_name])

        if datastore == 'file': # Create flask datastore
            create_server(BASE_FOLDER, test_fib_net_name, f'172.20.0.{cur_ip}', cur_port, latest_image,
                          datastore_platform, api, 'none', f'localhost', cur_port, datastore_name)
        elif datastore == 'elasticstack': # Create ElasticStack datastore
            es_names: list[str] = ['logstash', 'elasticsearch', 'kibana']
            es_ips: list[str] = [f'172.20.0.{es_ip}' for es_ip in range(cur_ip, cur_ip + 3)]
            es_ports: list[int] = [es_port for es_port in range(cur_port, cur_port + 3)]
            es_info = zip(es_names, es_ips, es_ports)
            create_elasticstack(
                BASE_FOLDER, test_fib_net_name, es_info, datastore_name, datastore_user, datastore_password
            )
            for es_name, es_ip, es_port in es_info:
                test_fib_net[f'{datastore_name}-{es_name}'] = {'ip': f'172.20.0.{es_ip}', 'port': es_port}
                cur_ip += 1
                cur_port += 1
        elif datastore == 'mongodb': # Create MongoDB datastore
            create_mongodb(
                BASE_FOLDER, test_fib_net_name, f'172.20.0.{cur_ip}', cur_port, datastore_name,
                datastore_user, datastore_password
            )
        elif datastore == 'postgres': # Create PostgreSQL datastore
            create_postgresql(
                BASE_FOLDER, test_fib_net_name, f'172.20.0.{cur_ip}', cur_port, datastore_name,
                datastore_user, datastore_password
            )

        # Prepare for next test datastore
        if datastore != 'elasticstack':
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
        if datastore != 'elasticstack':
            datastore_ip: str = test_fib_net[f'test-fib-{api}-{datastore}-datastore']['ip']
            datastore_port: int = test_fib_net[f'test-fib-{api}-{datastore}-datastore']['port']
        else:
            datastore_ip: str = test_fib_net[f'test-fib-{api}-{datastore}-datastore-logstash']['ip']
            datastore_port: int = test_fib_net[f'test-fib-{api}-{datastore}-datastore-logstash']['port']

        create_server(BASE_FOLDER, test_fib_net_name, f'172.20.0.{cur_ip}', cur_port, latest_image, platform, api,
                      datastore, datastore_ip, datastore_port, server_name, datastore_user, datastore_password)

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
