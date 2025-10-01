from shutil import copytree, rmtree
from os.path import exists
from os import mkdir
from yaml import dump
from KubeUtils import *


# Constants
USE_CASE_NUM: int = 3
TEMPLATE_FOLDER: str = 'templates'


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
    print('Adding Chart.yaml...')
    with open(f'{base_folder}/{fs['outputFolder']}/Chart.yaml', 'w') as chart_file:
        chart_file.write(dump(chart_dict))


def create_helm_tls_file_function(tls_folder, tls_filename, tls_ext):
    return (
        '{{ .Files.Get "' + tls_folder + '/' +
        f'{tls_filename}.{tls_ext}" | b64enc | quote ' + '}}'
    )


def create_secret_templates(dns, fs, stage, namespace_name, template_folder):
    # Create Ingress secrets
    ingress_secret_data = {
        'tls.key': create_helm_tls_file_function(fs['tlsFolder'], dns['ingressName'], fs['keyExt']),
        'tls.crt': create_helm_tls_file_function(fs['tlsFolder'], dns['ingressName'], fs['certExt'])
    }
    ingress_secret = create_secret(
        dns['ingressName'], namespace_name, 'kubernetes.io/TLS', ingress_secret_data
    )
    print(f'Adding {TEMPLATE_FOLDER}/{ingress_secret['metadata']['name']}.yaml...')
    with open(f'{template_folder}/{ingress_secret['metadata']['name']}.yaml', 'w') as ingress_secret_file:
        ingress_secret_file.write(dump(ingress_secret).replace("'{", "{").replace("}'", "}"))

    # Create server stage secrets
    for i in range(stage['count']):
        server_stage_index = i + 1
        server_stage_name = f'{stage['namePrefix']}-{server_stage_index}'

        server_stage_secret_data = {
            'self.key': create_helm_tls_file_function(fs['tlsFolder'], server_stage_name, fs['keyExt']),
            'self.crt': create_helm_tls_file_function(fs['tlsFolder'], server_stage_name, fs['certExt']),
            'ca.crt': create_helm_tls_file_function(fs['tlsFolder'], dns['caName'], fs['certExt']),
        }
        server_stage_secret = create_secret(
            server_stage_name, namespace_name, 'Opaque', server_stage_secret_data
        )
        print(f'Adding {TEMPLATE_FOLDER}/{server_stage_secret['metadata']['name']}.yaml...')
        with open(f'{template_folder}/{server_stage_secret['metadata']['name']}.yaml', 'w') as server_stage_secret_file:
            server_stage_secret_file.write(dump(server_stage_secret).replace("'{", "{").replace("}'", "}"))


def create_deployment_template(name, namespace_name, replica_count, pod_labels, restart_policy, image_name, stage,
                               platform, dns, envs, template_folder, deploy_node_selector=None, deploy_labels=None):
    # Start configuration
    deployment = create_deployment(
        name, namespace_name, replica_count, pod_labels, restart_policy,
        node_selector=deploy_node_selector, labels=deploy_labels
    )

    # Create liveness probe for all containers
    probe_settings = {
        'exec': {
            'command': [platform['healthcheckCMD']]
        },
        'initialDelaySeconds': 10,
        'periodSeconds': 10,
        'timeoutSeconds': 5,
        'failureThreshold': 3
    }

    # Create settings for each stage
    for i in range(stage['count']):
        server_stage_index = i + 1
        server_stage_name = f'{stage['namePrefix']}-{server_stage_index}'

        # Create port bindings
        port_bindings = [{
            'containerPort': platform['startPort'] + server_stage_index,
            'protocol': 'TCP'
        }]

        # Create the destination port
        if server_stage_index < stage['count']:
            dest_port = platform['startPort'] + server_stage_index + 1
        elif server_stage_index == stage['count']:
            dest_port = platform['startPort'] + 1
        else:
            raise IndexError(f'{server_stage_index} is invalid.')

        # Create environmental variables
        env_settings = [
            {'name': 'SERVER_STAGE_COUNT', 'value': f'{stage['count']}'},
            {'name': 'SERVER_STAGE_INDEX', 'value': f'{server_stage_index}'},
            {'name': 'SELF_LISTENING_ADDRESS', 'value': dns['defaultListeningIP']},
            {'name': 'SELF_HEALTHCHECK_ADDRESS', 'value': dns['default']},
            {'name': 'SELF_PORT', 'value': f'{platform['startPort'] + server_stage_index}'},
            {'name': 'SECRET_KEY_TARGET', 'value': envs['selfKeyTarget']},
            {'name': 'SECRET_CERT_TARGET', 'value': envs['selfCertTarget']},
            {'name': 'SECRET_CA_CERT_TARGET', 'value': envs['caCertTarget']},
            {'name': 'DEST_ADDRESS', 'value': dns['default']},
            {'name': 'DEST_PORT', 'value': f'{dest_port}'},
            {'name': 'THROTTLE_INTERVAL', 'value': f'{envs['throttleInterval']}'},
            {'name': 'UPPER_BOUND', 'value': f'{envs['upperBound']}'}
        ]

        # Create volume mount
        secret_mount = [{
            'name': f'{server_stage_name}-secret-mount',
            'mountPath': envs['tlsTarget'],
            'readOnly': True
        }]

        # Add containers and volumes
        deployment['spec']['template']['spec']['containers'].append(
            create_container(server_stage_name, image_name, port_bindings, env_settings, secret_mount, probe_settings)
        )
        deployment['spec']['template']['spec']['volumes'].append(
            create_secret_volume(f'{server_stage_name}-secret-mount', f'{server_stage_name}-secret')
        )

    # Save deployment
    print(f'Adding {TEMPLATE_FOLDER}/{deployment['metadata']['name']}.yaml...')
    with open(f'{template_folder}/{deployment['metadata']['name']}.yaml', 'w') as server_stage_secret_file:
        server_stage_secret_file.write(dump(deployment))


def create_chart(base_folder, project_folder, setup_config):
    # Create subgroups to save space
    stage = setup_config['stage']
    fs = setup_config['fs']
    helm = setup_config['kube']['helm']
    dns = setup_config['dns']
    kube = setup_config['kube']
    platform = setup_config['platform']
    envs = setup_config['envs']

    # Create folders for chart items
    print('Setting up Helm chart folder...')
    if not exists(f'{base_folder}/{fs['outputFolder']}'):
        mkdir(f'{base_folder}/{fs['outputFolder']}')
    if not exists(f'{base_folder}/{fs['outputFolder']}/{TEMPLATE_FOLDER}'):
        mkdir(f'{base_folder}/{fs['outputFolder']}/{TEMPLATE_FOLDER}')

    print('Copying TLS materials into chart folder...')
    if exists(f'{base_folder}/{fs['outputFolder']}/{fs['tlsFolder']}'):
        rmtree(f'{base_folder}/{fs['outputFolder']}/{fs['tlsFolder']}')
    copytree(f'{project_folder}/{fs['tlsFolder']}', f'{base_folder}/{fs["outputFolder"]}/{fs['tlsFolder']}')

    # Create chart yaml file
    create_chart_items(base_folder, stage, fs, helm)

    # Set up variables for rest of method
    use_case_name = f'{stage['useCasePrefix']}-{USE_CASE_NUM}'
    template_folder = f'{base_folder}/{fs['outputFolder']}/{TEMPLATE_FOLDER}'
    image_name = open(f'{project_folder}/{fs['imageVersionFp']}').read()

    # Create kubernetes namespace
    namespace_hook = {'stages': 'pre-install', 'weight': '-2', 'policy': 'hook-failed'}
    namespace = create_namespace(use_case_name, general_level='baseline', hook=namespace_hook)
    namespace_name = namespace['metadata']['name']
    print(f'Adding {TEMPLATE_FOLDER}/{namespace_name}.yaml...')
    with open(f'{template_folder}/{namespace_name}.yaml', 'w') as namespace_file:
        namespace_file.write(dump(namespace))

    # Create admission policies
    a_policy_hook = {'stages': 'pre-install', 'weight': '-1', 'policy': 'hook-failed'}
    a_policy_constraints = {
        'resourceRules': [{
            'apiGroups': ['apps'],
            'apiVersions': ['v1'],
            'operations': ['CREATE', 'UPDATE'],
            'resources': ['deployments']
        }]
    }
    a_policy_validations = [{
        'expression': f"object.spec.template.spec.containers.all(c, c.image == '{image_name}')",
        'message': f"Deployment containers can only use the image {image_name}."
    }]
    a_policy_binding_valid_actions = ['Deny']
    a_policy, a_policy_binding = create_validating_admission_policy(
        use_case_name, 'Fail', a_policy_constraints, a_policy_validations, a_policy_binding_valid_actions,
        namespace_name, hook=a_policy_hook
    )

    print(f'Adding {TEMPLATE_FOLDER}/{a_policy['metadata']['name']}.yaml...')
    with open(f'{template_folder}/{a_policy['metadata']['name']}.yaml', 'w') as a_policy_file:
        a_policy_file.write(dump(a_policy))

    print(f'Adding {TEMPLATE_FOLDER}/{a_policy_binding['metadata']['name']}.yaml...')
    with open(f'{template_folder}/{a_policy_binding['metadata']['name']}.yaml', 'w') as a_policy_binding_file:
        a_policy_binding_file.write(dump(a_policy_binding))

    # Create secrets
    create_secret_templates(dns, fs, stage, namespace_name, template_folder)

    # Create deployment
    pod_labels = {
        'app.kubernetes.io/name': f'{use_case_name}-app'
    }
    create_deployment_template(
        use_case_name, namespace_name, kube['replicas'], pod_labels, kube['podRestartPolicy'], image_name, stage,
        platform, dns, envs, template_folder
    )

    # Create service
    port_bindings = [{
        'port': platform['startPort'] + 1,
        'protocol': 'TCP',
        'targetPort': platform['startPort'] + 1
    }]
    service = create_service(use_case_name, namespace_name, pod_labels, port_bindings)
    print(f'Adding {TEMPLATE_FOLDER}/{service['metadata']['name']}.yaml...')
    with open(f'{template_folder}/{service['metadata']['name']}.yaml', 'w') as service_file:
        service_file.write(dump(service))

    # Create ingress
    ingress_paths = [{
        'path': dns['startAPI'],
        'pathType': 'Exact',
        'backend': {
            'service': {
                'name': f'{use_case_name}-service',
                'port': {
                    'number': platform['startPort'] + 1
                }
            }
        }
    }]
    ingress = create_ingress(
        use_case_name, namespace_name, 'nginx', dns['domain'], f'{dns['ingressName']}-secret',
        ingress_paths
    )
    print(f'Adding {TEMPLATE_FOLDER}/{ingress['metadata']['name']}.yaml...')
    with open(f'{template_folder}/{ingress['metadata']['name']}.yaml', 'w') as ingress_file:
        ingress_file.write(dump(ingress))

    # Create network policy
    port_bindings = [{
        'port': platform['startPort'] + 1,
        'protocol': 'TCP'
    }]
    network_policy = create_network_policy(
        use_case_name, namespace_name, {'matchLabels': pod_labels}, f'{dns['defaultIP']}/32',
        port_bindings
    )
    print(f'Adding {TEMPLATE_FOLDER}/{network_policy['metadata']['name']}.yaml...')
    with open(f'{template_folder}/{network_policy['metadata']['name']}.yaml', 'w') as network_policy_file:
        network_policy_file.write(dump(network_policy))
