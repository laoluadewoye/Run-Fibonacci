from os.path import abspath, dirname, exists
from os import mkdir
from json import loads
from GenerateTLS import create_tls_materials


# Get base folder
BASE_FOLDER: str = abspath(dirname(__file__))

# Load configuration
with open('./setup_config.json') as setup_file:
    setup_config: dict = loads(setup_file.read())

# Create output folder
if not exists(f'{BASE_FOLDER}/{setup_config['fs']['outputFolder']}'):
    mkdir(f'{BASE_FOLDER}/{setup_config['fs']['outputFolder']}')

# Run create tls
tls_materials: dict = create_tls_materials(BASE_FOLDER, setup_config)
print(tls_materials)
