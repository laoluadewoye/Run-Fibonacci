from shutil import copytree, rmtree, copy
from os.path import exists
from os import mkdir
from yaml import dump
from KubeUtils import *


# Constants
USE_CASE_NUM: int = 3


def create_chart_items(base_folder, stage, fs, helm):
    # Create chart yaml configuration
    chart_dict = {
        'apiVersion': helm['apiVersion'],
        'name': f'{stage['useCasePrefix']}-{USE_CASE_NUM}',
        'version': f'{open(f'{base_folder}/latest_program.adoc').read()}',
        'kubeVersion': helm['allowedKubeVersion'],
        'type': helm['chartType'],
        'home': helm['home'],
    }

    # Save chart to file
    with open(f'{base_folder}/{fs['outputFolder']}/Chart.yaml', 'w') as chart_file:
        chart_file.write(dump(chart_dict))

    # Copy helm ignore file into chart folder
    copy(f'{base_folder}/.helmignore', f'{base_folder}/{fs["outputFolder"]}/.helmignore')


def create_chart(base_folder, project_folder, setup_config):
    # Create subgroups to save space
    stage = setup_config['stage']
    fs = setup_config['fs']
    helm = setup_config['kube']['helm']
    dns = setup_config['dns']
    network = setup_config['platform']['network']
    envs = setup_config['envs']

    # Create folders for chart items
    if not exists(f'{base_folder}/{fs['outputFolder']}'):
        mkdir(f'{base_folder}/{fs['outputFolder']}')
    if not exists(f'{base_folder}/{fs['outputFolder']}/templates'):
        mkdir(f'{base_folder}/{fs['outputFolder']}/templates')
    if exists(f'{base_folder}/{fs['outputFolder']}/tls'):
        rmtree(f'{base_folder}/{fs['outputFolder']}/tls')
    copytree(f'{project_folder}/tls', f'{base_folder}/{fs["outputFolder"]}/tls')

    # Create chart yaml file
    create_chart_items(base_folder, stage, fs, helm)

    # Set template folder filepath for rest of method
    template_folder = f'{base_folder}/{fs['outputFolder']}/templates'

    # Create kubernetes namespace
    namespace = create_namespace(f'{stage['useCasePrefix']}-{USE_CASE_NUM}', general_level='restricted')
    with open(f'{template_folder}/{namespace['metadata']['name']}.yaml', 'w') as namespace_file:
        namespace_file.write(dump(namespace))
