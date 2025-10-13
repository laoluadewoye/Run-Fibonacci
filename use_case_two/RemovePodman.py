from pathlib import Path
from json import loads
from subprocess import run


if __name__ == '__main__':
    # Get base folder
    BASE_FOLDER: Path = Path(__file__).resolve().parent

    # Get project folder
    project_folder: Path = Path(BASE_FOLDER).resolve().parent

    # Load configuration from the project folder
    with open(f'{project_folder}/setup_config.json') as setup_file:
        setup_config: dict = loads(setup_file.read())

    # Stop containers
    print('Stopping containers...')
    run([
        'podman', 'stop', f'--filter=label={setup_config['stage']['useCasePrefix']}',
    ])

    # Remove containers
    print('Removing containers...')
    run([
        'podman', 'rm', f'--filter=label={setup_config['stage']['useCasePrefix']}',
    ])

    # Remove secrets
    print('Nuking secrets...')
    run([
        'podman', 'secret', 'rm', '--all',
    ])

    # Remove network
    print('Removing network...')
    run([
        'podman', 'network', 'rm', f'{setup_config['engine']['network']['name']}',
    ])
