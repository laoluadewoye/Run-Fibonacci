from shutil import copytree, rmtree
from os.path import exists
from os import mkdir
from yaml import dump
from KubeUtils import *


def create_chart_items(base_folder, use_case_num, stage, fs, helm):
    # Create chart yaml configuration
    chart_dict = {
        'apiVersion': helm['apiVersion'],
        'name': f'{stage['useCasePrefix']}-{use_case_num}',
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


def create_secret_templates(use_case_name, dns, fs, stage, envs, namespace_name, template_name, template_folder):
    # Create Ingress secrets
    ingress_secret_data = {
        'tls.key': create_helm_tls_file_function(fs['tlsFolder'], dns['ingressName'], fs['keyExt']),
        'tls.crt': create_helm_tls_file_function(fs['tlsFolder'], dns['ingressName'], fs['certExt'])
    }

    ingress_secret = create_secret(
        f'{use_case_name}-{dns['ingressName']}', namespace_name, 'kubernetes.io/TLS', ingress_secret_data
    )
    print(f'Adding {template_name}/{ingress_secret['metadata']['name']}.yaml...')
    with open(f'{template_folder}/{ingress_secret['metadata']['name']}.yaml', 'w') as ingress_secret_file:
        ingress_secret_file.write(dump(ingress_secret).replace("'{", "{").replace("}'", "}"))

    # Create server stage secrets
    for i in range(stage['count']):
        server_stage_index = i + 1
        server_stage_name = f'{stage['namePrefix']}-{server_stage_index}'

        server_stage_secret_data = {
            f'{envs['selfName']}.{fs['keyExt']}': create_helm_tls_file_function(
                fs['tlsFolder'], server_stage_name, fs['keyExt']
            ),
            f'{envs['selfName']}.{fs['certExt']}': create_helm_tls_file_function(
                fs['tlsFolder'], server_stage_name, fs['certExt']
            ),
            f'{dns['caName']}.{fs['certExt']}': create_helm_tls_file_function(
                fs['tlsFolder'], dns['caName'], fs['certExt']
            ),
        }
        server_stage_secret = create_secret(
            server_stage_name, namespace_name, 'Opaque', server_stage_secret_data
        )
        print(f'Adding {template_name}/{server_stage_secret['metadata']['name']}.yaml...')
        with open(f'{template_folder}/{server_stage_secret['metadata']['name']}.yaml', 'w') as server_stage_secret_file:
            server_stage_secret_file.write(dump(server_stage_secret).replace("'{", "{").replace("}'", "}"))


def create_deployment_template(server_stage_index, name, namespace_name, replica_count, pod_labels, restart_policy,
                               probe_settings, image_name, template_name, template_folder, platform, stage, dns, envs, fs, deploy_node_selector=None,
                               deploy_labels=None):
    # Start deployment
    deployment = create_deployment(
        name, namespace_name, replica_count, pod_labels, restart_policy,
        node_selector=deploy_node_selector, labels=deploy_labels
    )

    # Create port bindings
    port_bindings = [{
        'containerPort': platform['startPort'],
        'protocol': 'TCP'
    }]

    # Create destination service
    if server_stage_index < stage['count']:
        dest_service = f'{stage['namePrefix']}-{server_stage_index + 1}-service'
    elif server_stage_index == stage['count']:
        dest_service = f'{stage['namePrefix']}-1-service'
    else:
        raise IndexError(f'{server_stage_index} is invalid.')

    # Create environmental variables
    env_settings = [
        {'name': 'SERVER_STAGE_COUNT', 'value': f'{stage['count']}'},
        {'name': 'SERVER_STAGE_INDEX', 'value': f'{server_stage_index}'},
        {'name': 'SELF_LISTENING_ADDRESS', 'value': dns['defaultListeningIP']},
        {'name': 'SELF_HEALTHCHECK_ADDRESS', 'value': dns['default']},
        {'name': 'SELF_PORT', 'value': f'{platform['startPort']}'},
        {'name': 'SECRET_KEY_TARGET', 'value': f'{envs['tlsTarget']}/{envs['selfName']}.{fs['keyExt']}'},
        {'name': 'SECRET_CERT_TARGET', 'value': f'{envs['tlsTarget']}/{envs['selfName']}.{fs['certExt']}'},
        {'name': 'SECRET_CA_CERT_TARGET', 'value': f'{envs['tlsTarget']}/{dns['caName']}.{fs['certExt']}'},
        {'name': 'DEST_ADDRESS', 'value': dest_service},
        {'name': 'DEST_PORT', 'value': f'{platform['startPort']}'},
        {'name': 'THROTTLE_INTERVAL', 'value': f'{envs['throttleInterval']}'},
        {'name': 'UPPER_BOUND', 'value': f'{envs['upperBound']}'}
    ]

    # Create volume mount
    secret_mount = [{
        'name': f'{name}-secret-mount',
        'mountPath': envs['tlsTarget'],
        'readOnly': True
    }]

    # Add containers and volumes
    deployment['spec']['template']['spec']['containers'].append(
        create_container(name, image_name, port_bindings, env_settings, secret_mount, probe_settings)
    )
    deployment['spec']['template']['spec']['volumes'].append(
        create_secret_volume(f'{name}-secret-mount', f'{name}-secret')
    )

    # Save deployment
    print(f'Adding {template_name}/{deployment['metadata']['name']}.yaml...')
    with open(f'{template_folder}/{deployment['metadata']['name']}.yaml', 'w') as deployment_file:
        deployment_file.write(dump(deployment))


def create_chart(base_folder, project_folder, setup_config, use_case_num):
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
    if not exists(f'{base_folder}/{fs['outputFolder']}/{helm['templateFolder']}'):
        mkdir(f'{base_folder}/{fs['outputFolder']}/{helm['templateFolder']}')

    print('Copying TLS materials into chart folder...')
    if exists(f'{base_folder}/{fs['outputFolder']}/{fs['tlsFolder']}'):
        rmtree(f'{base_folder}/{fs['outputFolder']}/{fs['tlsFolder']}')
    copytree(f'{project_folder}/{fs['tlsFolder']}', f'{base_folder}/{fs["outputFolder"]}/{fs['tlsFolder']}')

    # Create chart yaml file
    create_chart_items(base_folder, use_case_num, stage, fs, helm)

    # Set up variables for rest of method
    use_case_name = f'{stage['useCasePrefix']}-{use_case_num}'
    template_folder = f'{base_folder}/{fs['outputFolder']}/{helm['templateFolder']}'
    image_name = open(f'{project_folder}/{fs['imageVersionFp']}').read()

    # Create kubernetes namespace
    namespace_hook = {
        'helm.sh/hook': helm['hook'], 'helm.sh/hook-weight': '-2', 'helm.sh/hook-delete-policy': helm['hookPolicy']
    }
    namespace = create_namespace(use_case_name, general_level=kube['namespacePolicy'], hook=namespace_hook)
    namespace_name = namespace['metadata']['name']
    print(f'Adding {helm['templateFolder']}/{namespace_name}.yaml...')
    with open(f'{template_folder}/{namespace_name}.yaml', 'w') as namespace_file:
        namespace_file.write(dump(namespace))

    # Create admission policies
    a_policy_hook = {
        'helm.sh/hook': helm['hook'], 'helm.sh/hook-weight': '-1', 'helm.sh/hook-delete-policy': helm['hookPolicy']
    }
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

    print(f'Adding {helm['templateFolder']}/{a_policy['metadata']['name']}.yaml...')
    with open(f'{template_folder}/{a_policy['metadata']['name']}.yaml', 'w') as a_policy_file:
        a_policy_file.write(dump(a_policy))

    print(f'Adding {helm['templateFolder']}/{a_policy_binding['metadata']['name']}.yaml...')
    with open(f'{template_folder}/{a_policy_binding['metadata']['name']}.yaml', 'w') as a_policy_binding_file:
        a_policy_binding_file.write(dump(a_policy_binding))

    # Create secrets
    create_secret_templates(use_case_name, dns, fs, stage, envs, namespace_name, helm['templateFolder'], template_folder)

    # Loop through server stages
    pod_labels = {
        'app.kubernetes.io/name': f'{use_case_name}-app'
    }
    probe_settings = {
        'exec': {
            'command': [platform['healthcheckCMD']]
        },
        'initialDelaySeconds': 10,
        'periodSeconds': 10,
        'timeoutSeconds': 5,
        'failureThreshold': 3
    }

    for i in range(stage['count']):
        server_stage_index = i + 1
        server_stage_name = f'{stage['namePrefix']}-{server_stage_index}'
        pod_labels['app.kubernetes.io/component'] = server_stage_name

        # Create deployment
        create_deployment_template(
            server_stage_index, server_stage_name, namespace_name, kube['replicas'], pod_labels,
            kube['podRestartPolicy'], probe_settings, image_name, helm['templateFolder'], template_folder,
            platform, stage, dns, envs, fs
        )

        # Create service
        port_bindings = [{
            'port': platform['startPort'],
            'protocol': 'TCP',
            'targetPort': platform['startPort']
        }]
        service = create_service(server_stage_name, namespace_name, pod_labels, port_bindings)
        print(f'Adding {helm['templateFolder']}/{service['metadata']['name']}.yaml...')
        with open(f'{template_folder}/{service['metadata']['name']}.yaml', 'w') as service_file:
            service_file.write(dump(service))

    # Create ingress
    ingress_paths = [{
        'path': f'/v{use_case_num}{dns['startAPI']}',
        'pathType': 'Exact',
        'backend': {
            'service': {
                'name': f'{stage['namePrefix']}-1-service',
                'port': {
                    'number': platform['startPort']
                }
            }
        }
    }]
    ingress = create_ingress(
        use_case_name, namespace_name, 'nginx', dns['domain'],
        f'{use_case_name}-{dns['ingressName']}-secret', ingress_paths
    )
    print(f'Adding {helm['templateFolder']}/{ingress['metadata']['name']}.yaml...')
    with open(f'{template_folder}/{ingress['metadata']['name']}.yaml', 'w') as ingress_file:
        ingress_file.write(dump(ingress))

    # Create network policy
    port_bindings = [{
        'port': platform['startPort'],
        'protocol': 'TCP'
    }]
    network_selector = {
        'matchLabels': {
            'app.kubernetes.io/name': f'{use_case_name}-app'
        }
    }
    network_policy = create_network_policy(
        use_case_name, namespace_name, network_selector, f'{dns['defaultIP']}/32', port_bindings
    )
    print(f'Adding {helm['templateFolder']}/{network_policy['metadata']['name']}.yaml...')
    with open(f'{template_folder}/{network_policy['metadata']['name']}.yaml', 'w') as network_policy_file:
        network_policy_file.write(dump(network_policy))
