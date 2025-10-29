from pathlib import Path
from os.path import exists
from subprocess import run, CompletedProcess
from base64 import b64encode
from secrets import token_bytes
from itertools import product
from ipaddress import ip_address, IPv4Address
from uuid import uuid4
from time import sleep
from requests import request, Response
from json import dumps


def create_server(base_folder: Path, server_network: str, server_ip: str, server_port: int, server_image: str,
                  server_platform: str, server_api: str, container_name: str, server_datastore: str = 'none',
                  server_datastore_addr: str = 'N/A', server_datastore_port: int = -1,
                  server_datastore_user: str = 'N/A', server_datastore_pass: str = 'N/A') -> None:
    # Check if test server already exist and delete if needed
    server_output: CompletedProcess = run(
        [command, 'ps', '-a', '--filter', f'name={container_name}'], capture_output=True, text=True
    )
    if server_output.stdout.split('\n')[1] != '':
        run([command, 'stop', container_name])
        run([command, 'rm', container_name])

    run([
        command, 'run', '-d', '-p', f'{server_port}:{server_port}',
        f'--network={server_network}', f'--ip={server_ip}',
        '-v', f'{base_folder}/test_ca.key:/usr/src/app/ca.key',
        '-v', f'{base_folder}/test_ca.crt:/usr/src/app/ca.crt',
        '-e', f'API={server_api}',
        '-e', f'DATASTORE_TYPE={server_datastore}',
        '-e', f'NETWORK_SELF_PORT={server_port}',
        '-e', f'NETWORK_DEST_PORT={server_port}',
        '-e', f'NETWORK_DATASTORE_ADDRESS={server_datastore_addr}',
        '-e', f'NETWORK_DATASTORE_PORT={server_datastore_port}',
        '-e', f'DATASTORE_AUTH_USERNAME={server_datastore_user}',
        '-e', f'DATASTORE_AUTH_PASSWORD={server_datastore_pass}',
        '-e', f'TLS_SAN_IPS=127.0.0.1,{server_ip}',
        '--name', container_name,
        f'{server_image}-{server_platform}'
    ])


def create_elasticstack(base_folder: Path, server_network: str, server_info: zip, container_name: str,
                        server_datastore_user: str, server_datastore_pass: str) -> None:
    # Set ElasticStack defaults for later
    es_ip: str = ''
    es_port: int = 9200
    es_user: str = 'elastic'
    es_ca_cert_name: str = 'test_es_ca.crt'
    kibana_port: int = 5601
    kibana_user: str = 'kibana_system'
    kibana_password: str = ''
    logstash_port: int = 9600
    logstash_user: str = 'logstash_es'
    logstash_password: str = server_datastore_pass

    # Loop through datastore components
    for server_component, server_ip, server_port in server_info:
        print(f'\nComponent: {server_component}')
        print(f'IP Address: {server_ip}')
        print(f'Port: {server_port}')

        # Check if test datastore already exist and delete if needed
        component_output: CompletedProcess = run(
            [command, 'ps', '-a', '--filter', f'name={container_name}-{server_component}'], capture_output=True,
            text=True
        )
        if component_output.stdout.split('\n')[1] != '':
            run([command, 'stop', f'{container_name}-{server_component}'])
            run([command, 'rm', f'{container_name}-{server_component}'])

        # Start components
        if server_component == 'elasticsearch':
            # Set ip address for later
            es_ip = server_ip

            # Start server component
            run([
                command, 'run', '-d', '-m', '1GB', '-p', f'{server_port}:{es_port}',
                f'--network={server_network}', f'--ip={server_ip}',
                '--name', f'{container_name}-{server_component}',
                'docker.elastic.co/elasticsearch/elasticsearch:9.2.0'
            ])

            # Wait for elasticsearch to finish startup tasks
            for i in range(20, 0, -1):
                print(f'Waiting {i} seconds for elasticsearch to start before calling for auth...')
                sleep(1)

            # Obtain elastic password
            component_output: CompletedProcess = run(
                [
                    command, 'exec', f'{container_name}-{server_component}',
                    '/usr/share/elasticsearch/bin/elasticsearch-reset-password', '--batch', '--username', es_user
                ],
                capture_output=True, text=True
            )
            es_password = component_output.stdout[-21:-1]
            print('Elasticsearch password created.')

            # Copy Elasticsearch's CA cert to filesystem
            run([
                command, 'cp', f'{container_name}-{server_component}:/usr/share/elasticsearch/config/certs/http_ca.crt',
                f'{base_folder}/{es_ca_cert_name}'
            ])
            print('Elasticsearch CA cert saved.')

            # Obtain kibana password
            component_output: CompletedProcess = run(
                [
                    command, 'exec', f'{container_name}-{server_component}',
                    '/usr/share/elasticsearch/bin/elasticsearch-reset-password', '--batch', '--username', kibana_user
                ],
                capture_output=True, text=True
            )
            kibana_password = component_output.stdout[-21:-1]
            print('Kibana password created.')

            # Save information
            with open(f'{base_folder}/test_es_credentials.txt', 'w') as es_cred_file:
                es_cred_file.write(f'es user: {es_user}\n')
                es_cred_file.write(f'es password: {es_password}\n')
                es_cred_file.write(f'kibana user: {kibana_user}\n')
                es_cred_file.write(f'kibana password: {kibana_password}\n')

            # Create logstash user
            request(
                method='POST',
                url=f'https://localhost:{server_port}/_security/role/logstash_writer',
                auth=(es_user, es_password),
                json={
                    'cluster': ['manage_index_templates', 'monitor', 'manage_ilm'],
                    'indices': [
                        {
                            'names': ['logstash-*', '*datastore'],
                            'privileges': ['write', 'create', 'create_index', 'manage', 'manage_ilm']
                        }
                    ]
                },
                verify=f'{base_folder}/{es_ca_cert_name}'
            )
            print('Logstash role created.')
            request(
                method='POST',
                url=f'https://localhost:{server_port}/_security/user/{logstash_user}',
                auth=(es_user, es_password),
                json={
                    'password' : logstash_password,
                    'roles' : [ 'logstash_writer'],
                    'full_name' : 'Logstash system account for Elasticsearch'
                },
                verify=f'{base_folder}/{es_ca_cert_name}'
            )
            print('Logstash user created.')
        elif server_component == 'kibana':
            run([
                command, 'run', '-d', '-m', '1GB', '-p', f'{server_port}:{kibana_port}',
                f'--network={server_network}', f'--ip={server_ip}',
                '-v', f'{base_folder}/{es_ca_cert_name}:/usr/share/kibana/config/certs/es_http_ca.crt',
                '-e', 'ELASTICSEARCH_SSL_CERTIFICATEAUTHORITIES=/usr/share/kibana/config/certs/es_http_ca.crt',
                '-e', f'ELASTICSEARCH_HOSTS=https://{es_ip}:{es_port}',
                '-e', f'ELASTICSEARCH_USERNAME={kibana_user}',
                '-e', f'ELASTICSEARCH_PASSWORD={kibana_password}',
                '-e', f'XPACK_ENCRYPTEDSAVEDOBJECTS_ENCRYPTIONKEY={b64encode(token_bytes(32)).decode()}',
                '--name', f'{container_name}-{server_component}',
                'docker.elastic.co/kibana/kibana:9.2.0'
            ])
        elif server_component == 'logstash':
            run([
                command, 'run', '-d', '-m', '1GB', '-p', f'{server_port}:{logstash_port}',
                f'--network={server_network}', f'--ip={server_ip}',
                '-v', f'{base_folder}/{es_ca_cert_name}:/usr/share/logstash/config/certs/es_http_ca.crt',
                '-v', f'{base_folder}/logstash_config.yml:/usr/share/logstash/config/logstash.yml',
                '-v', f'{base_folder}/logstash_pipeline.conf:/usr/share/logstash/pipeline/datastore.conf',
                '-e', f'API_HTTP_PORT={logstash_port}',
                '-e', f'HTTP_PLUGIN_PORT={server_port}',
                '-e', f'API_AUTH_BASIC_USERNAME={server_datastore_user}',
                '-e', f'API_AUTH_BASIC_PASSWORD={server_datastore_pass}',
                '-e', f'ELASTICSEARCH_HOST={es_ip}',
                '-e', f'ELASTICSEARCH_PORT={es_port}',
                '-e', f'ELASTICSEARCH_USERNAME={logstash_user}',
                '-e', f'ELASTICSEARCH_PASSWORD={logstash_password}',
                '--name', f'{container_name}-{server_component}',
                'docker.elastic.co/logstash/logstash:9.2.0'
            ])


def create_mongodb(base_folder: Path, server_network: str, server_info: zip, container_name: str,
                   server_datastore_user: str, server_datastore_pass: str) -> None:
    # Set Mongo defaults for later
    mongodb_ip: str = ''
    mongodb_port: int = -1

    # Loop through datastore components
    for server_component, server_ip, server_port in server_info:
        print(f'\nComponent: {server_component}')
        print(f'IP Address: {server_ip}')
        print(f'Port: {server_port}')

        # Check if test datastore already exist and delete if needed
        component_output: CompletedProcess = run(
            [command, 'ps', '-a', '--filter', f'name={container_name}-{server_component}'], capture_output=True,
            text=True
        )
        if component_output.stdout.split('\n')[1] != '':
            run([command, 'stop', f'{container_name}-{server_component}'])
            run([command, 'rm', f'{container_name}-{server_component}'])

        # Start components
        if server_component == 'mongodb':
            mongodb_ip = server_ip
            mongodb_port = server_port

            run([
                command, 'run', '-d', '-p', f'{server_port}:{server_port}',
                f'--network={server_network}', f'--ip={server_ip}',
                '-e', f'MONGO_INITDB_ROOT_USERNAME={server_datastore_user}',
                '-e', f'MONGO_INITDB_ROOT_PASSWORD={server_datastore_pass}',
                '--name', f'{container_name}-{server_component}',
                'docker.io/library/mongo:8.0.15-noble', '--port', f'{server_port}'
            ])
        elif server_component == 'mongo-express':
            run([
                command, 'run', '-d', '-p', f'{server_port}:{server_port}',
                f'--network={server_network}', f'--ip={server_ip}',
                '-e', f'PORT={server_port}',
                '-e', f'ME_CONFIG_BASICAUTH_USERNAME={server_datastore_user}',
                '-e', f'ME_CONFIG_BASICAUTH_PASSWORD={server_datastore_pass}',
                '-e', f'ME_CONFIG_MONGODB_ADMINUSERNAME={server_datastore_user}',
                '-e', f'ME_CONFIG_MONGODB_ADMINPASSWORD={server_datastore_pass}',
                '-e', f'ME_CONFIG_MONGODB_PORT={mongodb_port}',
                '-e', f'ME_CONFIG_MONGODB_SERVER={mongodb_ip}',
                '--name', f'{container_name}-{server_component}',
                'docker.io/library/mongo-express:1.0.2-20-alpine3.19'
            ])


def create_postgresql(base_folder: Path, server_network: str, server_info: zip, container_name: str,
                   server_datastore_user: str, server_datastore_pass: str) -> None:
    # Loop through datastore components
    for server_component, server_ip, server_port in server_info:
        print(f'\nComponent: {server_component}')
        print(f'IP Address: {server_ip}')
        print(f'Port: {server_port}')

        # Check if test datastore already exist and delete if needed
        component_output: CompletedProcess = run(
            [command, 'ps', '-a', '--filter', f'name={container_name}-{server_component}'], capture_output=True,
            text=True
        )
        if component_output.stdout.split('\n')[1] != '':
            run([command, 'stop', f'{container_name}-{server_component}'])
            run([command, 'rm', f'{container_name}-{server_component}'])

        # Start components
        if server_component == 'postgres':
            run([
                command, 'run', '-d', '-p', f'{server_port}:{server_port}',
                f'--network={server_network}', f'--ip={server_ip}',
                '-v', f'{base_folder}/postgres_init.sql:/docker-entrypoint-initdb.d/init.sql',
                '-e', f'PGPORT={server_port}',
                '-e', f'POSTGRES_USER={server_datastore_user}',
                '-e', f'POSTGRES_PASSWORD={server_datastore_pass}',
                '--name', f'{container_name}-{server_component}',
                'docker.io/library/postgres:18.0-alpine3.22',
            ])
        elif server_component == 'pgadmin':
            run([
                command, 'run', '-d', '-p', f'{server_port}:{server_port}',
                f'--network={server_network}', f'--ip={server_ip}',
                '-e', f'PGADMIN_DEFAULT_EMAIL={server_datastore_user}@test.com',
                '-e', f'PGADMIN_DEFAULT_PASSWORD={server_datastore_pass}',
                '-e', f'PGADMIN_LISTEN_ADDRESS=0.0.0.0',
                '-e', f'PGADMIN_LISTEN_PORT={server_port}',
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
datastores: list[str] = ['none', 'file', 'elasticstack', 'mongodb', 'postgresql']
test_combos = product(platforms, datastores)

# Start port settings
current_ip: IPv4Address = ip_address('172.20.0.0')
current_port: int = 8080

# Create test network
test_fib_net: dict = {}
test_fib_net_name: str = 'test-fib-net'
network_output = run([command, 'network', 'ls'], capture_output=True, text=True)
if test_fib_net_name not in network_output.stdout:
    run([command, 'network', 'create', '--subnet', f'{current_ip}/16', test_fib_net_name])
current_ip += 2

# Create datastore credentials
datastore_user: str = 'test-fib-user'
datastore_password: str = uuid4().hex + uuid4().hex.upper()
with open(f'{BASE_FOLDER}/test_credentials.txt', 'w') as cred_file:
    cred_file.writelines([f'{datastore_user}@test.com\n', f'{datastore_user}\n', f'{datastore_password}\n'])

# Set up other details
datastore_start_wait_time: int = 10
server_ping_wait_time: int = 5

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
        datastore_name: str = f'test-fib-{api}-{datastore}-datastore'

        if datastore == 'file': # Create Flask datastore
            print(f'IP Address: {current_ip}')
            print(f'Port: {current_port}')
            create_server(
                BASE_FOLDER, test_fib_net_name, str(current_ip), current_port, latest_image, datastore_platform, api,
                datastore_name
            )
            test_fib_net[datastore_name] = {'ip': str(current_ip), 'port': current_port}
            current_ip += 1
            current_port += 1
        elif datastore == 'elasticstack': # Create ElasticStack datastore
            ds_names: list[str] = ['elasticsearch', 'kibana', 'logstash']
            ds_ips: list[str] = [str(current_ip + i) for i in range(3)]
            ds_ports: list[int] = [current_port + i for i in range(3)]
            create_elasticstack(
                BASE_FOLDER, test_fib_net_name, zip(ds_names, ds_ips, ds_ports), datastore_name, datastore_user,
                datastore_password
            )
            for ds_name, ds_ip, ds_port in zip(ds_names, ds_ips, ds_ports):
                test_fib_net[f'{datastore_name}-{ds_name}'] = {'ip': ds_ip, 'port': ds_port}
                current_ip += 1
                current_port += 1
        elif datastore == 'mongodb': # Create MongoDB datastore
            ds_names: list[str] = ['mongodb', 'mongo-express']
            ds_ips: list[str] = [str(current_ip + i) for i in range(2)]
            ds_ports: list[int] = [current_port + i for i in range(2)]
            create_mongodb(
                BASE_FOLDER, test_fib_net_name, zip(ds_names, ds_ips, ds_ports), datastore_name, datastore_user,
                datastore_password
            )
            for ds_name, ds_ip, ds_port in zip(ds_names, ds_ips, ds_ports):
                test_fib_net[f'{datastore_name}-{ds_name}'] = {'ip': ds_ip, 'port': ds_port}
                current_ip += 1
                current_port += 1
        elif datastore == 'postgresql': # Create PostgreSQL datastore
            ds_names: list[str] = ['postgres', 'pgadmin']
            ds_ips: list[str] = [str(current_ip + i) for i in range(2)]
            ds_ports: list[int] = [current_port + i for i in range(2)]
            create_postgresql(
                BASE_FOLDER, test_fib_net_name, zip(ds_names, ds_ips, ds_ports), datastore_name, datastore_user,
                datastore_password
            )
            for ds_name, ds_ip, ds_port in zip(ds_names, ds_ips, ds_ports):
                test_fib_net[f'{datastore_name}-{ds_name}'] = {'ip': ds_ip, 'port': ds_port}
                current_ip += 1
                current_port += 1

    # Wait for datastores to spin up
    print('------------------------------------------------------------------')
    for i in range(datastore_start_wait_time, 0, -1):
        print(f'Waiting {i} seconds for datastores to spin up...')
        sleep(1)

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
        elif datastore == 'postgresql':
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
        for i in range(server_ping_wait_time, 0, -1):
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
with open('test_network.json', 'w') as net_file:
    net_file.write(dumps(test_fib_net, indent=4))
