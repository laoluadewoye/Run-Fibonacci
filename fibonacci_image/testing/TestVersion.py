from pathlib import Path
from yaml import load as yaml_load, Loader as yaml_loader, dump as yaml_dump
from toml import load as toml_load, dump as toml_dump
from os.path import exists
from subprocess import run, CompletedProcess
from itertools import product
from ipaddress import ip_address, IPv4Address
from uuid import uuid4
from time import sleep
from requests import request, Response


def create_server(base_folder: Path, server_network: str, server_ip: str, server_port: int, server_image: str,
                  server_platform: str, server_api: str, container_name: str, server_datastore: str = 'none',
                  server_datastore_addr: str = 'N/A', server_datastore_port: int = -1,
                  server_datastore_user: str = 'N/A', server_datastore_pass: str = 'N/A') -> None:
    run([
        command, 'run', '-d', '-p', f'{server_port}:{server_port}',
        f'--network={server_network}', f'--ip={server_ip}',
        '-v', f'{base_folder}/test_self.key:/run/secrets/self.key',
        '-v', f'{base_folder}/test_self.crt:/run/secrets/self.crt',
        '-v', f'{base_folder}/test_self.pem:/run/secrets/self.pem',
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
        '-e', 'SECRET_PEM_TARGET=/run/secrets/self.pem',
        '-e', 'SECRET_CA_CERT_TARGET=/run/secrets/ca.crt',
        '-e', 'DEST_ADDRESS=localhost',
        '-e', f'DEST_PORT={server_port}',
        '-e', f'DATASTORE_ADDRESS={server_datastore_addr}',
        '-e', f'DATASTORE_PORT={server_datastore_port}',
        '-e', 'DATASTORE_FILEPATH=/tmp/datastore.csv',
        '-e', 'DATASTORE_DEFAULT_FILEPATH=/tmp/default.csv',
        '-e', 'DATASTORE_OPERATIONS_FILEPATH=/tmp/operations.csv',
        '-e', f'DATASTORE_USER={server_datastore_user}',
        '-e', f'DATASTORE_PASSWORD={server_datastore_pass}',
        '-e', 'THROTTLE_INTERVAL=5',
        '-e', 'UPPER_BOUND=4000000000',
        '--name', container_name,
        f'{server_image}-{server_platform}'
    ])


def create_elasticstack(base_folder: Path, server_network: str, server_info: zip, container_name: str,
                        server_datastore_user: str, server_datastore_pass: str) -> None:
    for server_component, server_ip, server_port in server_info:
        if server_component == 'logstash':
            ...
        elif server_component == 'elasticsearch':
            ...
        elif server_component == 'kibana':
            ...


def create_mongodb(base_folder: Path, server_network: str, server_info: zip, container_name: str,
                   server_datastore_user: str, server_datastore_pass: str) -> None:
    mongodb_ip: str = ''
    mongodb_port: int = -1

    for server_component, server_ip, server_port in server_info:
        if server_component == 'mongodb':
            # Store ip address and port for later
            mongodb_ip = server_ip
            mongodb_port = server_port

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
                '-e', f'MONGO_INITDB_ROOT_USERNAME={server_datastore_user}',
                '-e', f'MONGO_INITDB_ROOT_PASSWORD={server_datastore_pass}',
                '--name', f'{container_name}-{server_component}',
                'docker.io/library/mongo:8.0.15-noble',
                '--config', '/etc/mongo/mongod.conf'
            ])
        elif server_component == 'mongo-express':
            # Run mongo-express interface
            run([
                command, 'run', '-d', '-p', f'{server_port}:{server_port}',
                f'--network={server_network}', f'--ip={server_ip}',
                '-v', f'{base_folder}/test_self.key:/run/secrets/self.key',
                '-v', f'{base_folder}/test_self.crt:/run/secrets/self.crt',
                '-e', f'PORT={server_port}',
                '-e', f'ME_CONFIG_BASICAUTH_USERNAME={server_datastore_user}',
                '-e', f'ME_CONFIG_BASICAUTH_PASSWORD={server_datastore_pass}',
                '-e', f'ME_CONFIG_MONGODB_ADMINUSERNAME={server_datastore_user}',
                '-e', f'ME_CONFIG_MONGODB_ADMINPASSWORD={server_datastore_pass}',
                '-e', f'ME_CONFIG_MONGODB_PORT={mongodb_port}',
                '-e', f'ME_CONFIG_MONGODB_SERVER={mongodb_ip}',
                '-e', 'ME_CONFIG_SITE_SSL_ENABLED=true',
                '-e', 'ME_CONFIG_SITE_SSL_CRT_PATH=/run/secrets/self.crt',
                '-e', 'ME_CONFIG_SITE_SSL_KEY_PATH=/run/secrets/self.key',
                '--name', f'{container_name}-{server_component}',
                'docker.io/library/mongo-express:1.0.2-20-alpine3.19'
            ])


def create_postgresql(base_folder: Path, server_network: str, server_info: zip, container_name: str,
                   server_datastore_user: str, server_datastore_pass: str) -> None:
    for server_component, server_ip, server_port in server_info:
        if server_component == 'postgres':
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
                '-e', f'POSTGRES_USER={server_datastore_user}',
                '-e', f'POSTGRES_PASSWORD={server_datastore_pass}',
                '--name', f'{container_name}-{server_component}',
                'docker.io/library/postgres:18.0-alpine3.22',
                '-c', 'config_file=/etc/postgresql/postgresql.conf'
            ])
        elif server_component == 'pgadmin':
            # Run pgadmin interface
            run([
                command, 'run', '-d', '-p', f'{server_port}:{server_port}',
                f'--network={server_network}', f'--ip={server_ip}',
                '-v', f'{base_folder}/test_self.key:/certs/server.key',
                '-v', f'{base_folder}/test_self-ca.crt:/certs/server.cert',
                '-e', f'PGADMIN_DEFAULT_EMAIL={server_datastore_user}@test.com',
                '-e', f'PGADMIN_DEFAULT_PASSWORD={server_datastore_pass}',
                '-e', f'PGADMIN_LISTEN_ADDRESS={server_ip}',
                '-e', f'PGADMIN_LISTEN_PORT={server_port}',
                '-e', f'PGADMIN_ENABLE_TLS=true',
                '--name', f'{container_name}-{server_component}',
                'docker.io/elestio/pgadmin:REL-9_8'
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
datastores: list[str] = ['none', 'file', 'mongodb', 'postgresql']
test_combos = product(platforms, datastores)

# Start port settings
current_ip: IPv4Address = ip_address('172.20.0.0')
current_port: int = 8080

# Create test network
test_fib_net: dict = {}
test_fib_net_name: str = 'test-fib-net'
run([command, 'network', 'create', '--subnet', f'{current_ip}/16', test_fib_net_name])
current_ip += 2

# Create datastore credentials
datastore_user: str = 'test-fib-user'
datastore_password: str = uuid4().hex

# Run the test containers
for api in apis:
    datastore_platform: str = 'alpine'

    # Create test datastores
    for datastore in datastores:
        print('------------------------------------------------------------------')
        print('Creating datastore running with the following details...')
        print(f'Platform: {datastore_platform.title()} (Only used for file datastore)')
        print(f'API: {api.upper()}')
        print(f'Datastore: {datastore.title()}')
        print(f'IP Address: {current_ip}')
        print(f'Port: {current_port}')
        datastore_name: str = f'test-fib-{api}-{datastore}-datastore'

        # Check if test datastore already exist and delete if needed
        output: CompletedProcess = run(
            [command, 'ps' , '-a' , '--filter', f'name={datastore_name}'], capture_output=True, text=True
        )
        if output.stdout.split('\n')[1] != '':
            run([command, 'stop', datastore_name])
            run([command, 'rm', datastore_name])

        if datastore == 'file': # Create flask datastore
            create_server(
                BASE_FOLDER, test_fib_net_name, str(current_ip), current_port, latest_image, datastore_platform, api,
                datastore_name
            )
            test_fib_net[datastore_name] = {'ip': str(current_ip), 'port': current_port}
            current_ip += 1
            current_port += 1
        elif datastore == 'elasticstack': # Create ElasticStack datastore
            ds_names: list[str] = ['logstash', 'elasticsearch', 'kibana']
            ds_ips: list[str] = [str(current_ip + i) for i in range(3)]
            ds_ports: list[int] = [current_port + i for i in range(3)]
            ds_info = zip(ds_names, ds_ips, ds_ports)
            create_elasticstack(
                BASE_FOLDER, test_fib_net_name, ds_info, datastore_name, datastore_user, datastore_password
            )
            for ds_name, ds_ip, ds_port in ds_info:
                test_fib_net[f'{datastore_name}-{ds_name}'] = {'ip': ds_ip, 'port': ds_port}
                current_ip += 1
                current_port += 1
        elif datastore == 'mongodb': # Create MongoDB datastore
            ds_names: list[str] = ['mongodb', 'mongo-express']
            ds_ips: list[str] = [str(current_ip + i) for i in range(2)]
            ds_ports: list[int] = [current_port + i for i in range(2)]
            ds_info = zip(ds_names, ds_ips, ds_ports)
            create_mongodb(
                BASE_FOLDER, test_fib_net_name, ds_info, datastore_name, datastore_user, datastore_password
            )
            for ds_name, ds_ip, ds_port in ds_info:
                test_fib_net[f'{datastore_name}-{ds_name}'] = {'ip': ds_ip, 'port': ds_port}
                current_ip += 1
                current_port += 1
        elif datastore == 'postgres': # Create PostgreSQL datastore
            ds_names: list[str] = ['postgres', 'pgadmin']
            ds_ips: list[str] = [str(current_ip + i) for i in range(2)]
            ds_ports: list[int] = [current_port + i for i in range(2)]
            ds_info = zip(ds_names, ds_ips, ds_ports)
            create_postgresql(
                BASE_FOLDER, test_fib_net_name, ds_info, datastore_name, datastore_user, datastore_password
            )
            for ds_name, ds_ip, ds_port in ds_info:
                test_fib_net[f'{datastore_name}-{ds_name}'] = {'ip': ds_ip, 'port': ds_port}
                current_ip += 1
                current_port += 1

    # Run combinations
    for platform, datastore in test_combos:
        # Create test server
        print('------------------------------------------------------------------')
        print('Testing fibonacci server running with the following combination...')
        print(f'Platform: {platform.title()}')
        print(f'API: {api.upper()}')
        print(f'Datastore: {datastore.title()}')
        print(f'IP Address: {current_ip}')
        print(f'Port: {current_port}')
        server_name: str = f'test-fib-{api}-{datastore}-{platform}-server'

        # Check if test server already exist and delete if needed
        output = run([command, 'ps', '-a', '--filter', f'name={server_name}'], capture_output=True, text=True)
        if output.stdout.split('\n')[1] != '':
            run([command, 'stop', server_name])
            run([command, 'rm', server_name])

        # Create test server
        if datastore == 'file':
            datastore_ip: str = test_fib_net[f'test-fib-{api}-{datastore}-datastore']['ip']
            datastore_port: int = test_fib_net[f'test-fib-{api}-{datastore}-datastore']['port']
        elif datastore == 'elasticstack':
            datastore_ip: str = test_fib_net[f'test-fib-{api}-{datastore}-datastore-logstash']['ip']
            datastore_port: int = test_fib_net[f'test-fib-{api}-{datastore}-datastore-logstash']['port']
        elif datastore == 'mongodb':
            datastore_ip: str = test_fib_net[f'test-fib-{api}-{datastore}-datastore-mongodb']['ip']
            datastore_port: int = test_fib_net[f'test-fib-{api}-{datastore}-datastore-mongodb']['port']
        elif datastore == 'postgres':
            datastore_ip: str = test_fib_net[f'test-fib-{api}-{datastore}-datastore-postgres']['ip']
            datastore_port: int = test_fib_net[f'test-fib-{api}-{datastore}-datastore-postgres']['port']
        else:
            datastore_ip = 'N/A'
            datastore_port = -1

        create_server(
            BASE_FOLDER, test_fib_net_name, str(current_ip), current_port, latest_image, platform, api, server_name,
            datastore, datastore_ip, datastore_port, datastore_user, datastore_password
        )

        # Wait for test server to spin up
        for i in range(5, 0, -1):
            print(f'Waiting {i} seconds for container to spin up...')
            sleep(1)

        # Send message to test server
        if api == 'rest':
            response: Response = request(
                method='GET',
                url=f'https://localhost:{current_port}/start',
                cert=(f'{BASE_FOLDER}/test_self.crt', f'{BASE_FOLDER}/test_self.key'),
                verify=f'{BASE_FOLDER}/test_ca.crt'
            )
            print('Response status code:', response.status_code)
            print('Response contents:', response.json())

        # Prepare for next test server
        test_fib_net[server_name] = {'ip': str(current_ip), 'port': current_port}
        current_ip += 1
        current_port += 1

print("Done. Use your container engine to stop and delete the container whenever you're done.")
