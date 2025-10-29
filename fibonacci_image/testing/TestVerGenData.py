from pathlib import Path
from requests import request, Response
from json import loads

# Create constants
BASE_FOLDER: Path = Path(__file__).resolve().parent

# Import test network topology
with open('test_network.json') as net_file:
    test_fib_net = loads(net_file.read())

# Loop through test network topology
for key, value in test_fib_net.items():
    # Skip datastores
    if 'datastore' in key:
        continue

    # Send message to test server
    if 'rest' in key:
        print('Sending message to', key)
        response: Response = request(
            method='GET',
            url=f'https://localhost:{value['port']}/start',
            cert=(f'{BASE_FOLDER}/test_self.crt', f'{BASE_FOLDER}/test_self.key'),
            verify=f'{BASE_FOLDER}/test_ca.crt'
        )
        print('Response status code:', response.status_code)
        print('Response contents:', response.json())

print("Done. Use your container engine to stop and delete the container whenever you're done.")
