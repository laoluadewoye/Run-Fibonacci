from shutil import copytree, rmtree
from os.path import exists
from os import mkdir
from yaml import dump
from KubeUtils import *
from pathlib import Path


def create_chart_items(base_folder: Path, use_case_num: int, stage: dict, fs: dict, helm: dict) -> None:
    # Create chart yaml configuration
    chart_dict: dict = {
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


def create_helm_tls_file_function(tls_folder: str, tls_filename: str, tls_ext: str) -> str:
    return '{{ .Files.Get "' + tls_folder + '/' + f'{tls_filename}.{tls_ext}" | b64enc | quote ' + '}}'


def create_secret_templates(use_case_name: str, dns: dict, fs: dict, stage: dict, envs: dict, namespace_name: str,
                            template_name: str, template_folder: str) -> None:
    # Create Ingress secrets
    ingress_secret_data: dict = {
        'tls.key': create_helm_tls_file_function(fs['tlsFolder'], dns['ingressName'], fs['keyExt']),
        'tls.crt': create_helm_tls_file_function(fs['tlsFolder'], dns['ingressName'], fs['certExt'])
    }
    ingress_secret: dict = create_secret(
        f'{use_case_name}-{dns['ingressName']}', namespace_name, 'kubernetes.io/TLS', ingress_secret_data
    )
    print(f'Adding {template_name}/{ingress_secret['metadata']['name']}.yaml...')
    with open(f'{template_folder}/{ingress_secret['metadata']['name']}.yaml', 'w') as ingress_secret_file:
        ingress_secret_file.write(dump(ingress_secret).replace("'{", "{").replace("}'", "}"))

    # Create server stage secrets
    for i in range(stage['count']):
        server_stage_index: int = i + 1
        server_stage_name: str = f'{stage['namePrefix']}-{server_stage_index}'

        server_stage_secret_data: dict = {
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
        server_stage_secret: dict = create_secret(
            server_stage_name, namespace_name, 'Opaque', server_stage_secret_data
        )
        print(f'Adding {template_name}/{server_stage_secret['metadata']['name']}.yaml...')
        with open(f'{template_folder}/{server_stage_secret['metadata']['name']}.yaml', 'w') as server_stage_secret_file:
            server_stage_secret_file.write(dump(server_stage_secret).replace("'{", "{").replace("}'", "}"))


def create_deployment_template(name: str, namespace_name: str, replica_count: int, pod_labels: dict,
                               restart_policy: str, image_name: str, stage: dict, engine: dict, dns: dict,
                               envs: dict, fs: dict, template_name: str, template_folder: str,
                               deploy_node_selector: dict = None, deploy_labels: dict = None) -> None:
    # Start configuration
    deployment: dict = create_deployment(
        name, namespace_name, replica_count, pod_labels, restart_policy,
        node_selector=deploy_node_selector, labels=deploy_labels
    )

    # Create liveness probe for all containers
    probe_settings: dict = {
        'exec': {
            'command': [engine['healthcheckCMD']]
        },
        'initialDelaySeconds': 10,
        'periodSeconds': 10,
        'timeoutSeconds': 5,
        'failureThreshold': 3
    }

    # Create settings for each stage
    for i in range(stage['count']):
        server_stage_index: int = i + 1
        server_stage_name: str = f'{stage['namePrefix']}-{server_stage_index}'

        # Create port bindings
        port_bindings: list[dict] = [{
            'containerPort': engine['startPort'] + server_stage_index,
            'protocol': 'TCP'
        }]

        # Create the destination port
        if server_stage_index < stage['count']:
            dest_port: int = engine['startPort'] + server_stage_index + 1
        elif server_stage_index == stage['count']:
            dest_port: int = engine['startPort'] + 1
        else:
            raise IndexError(f'{server_stage_index} is invalid.')

        # Create environmental variables
        env_settings: list[dict] = [
            {'name': 'SERVER_STAGE_COUNT', 'value': f'{stage['count']}'},
            {'name': 'SERVER_STAGE_INDEX', 'value': f'{server_stage_index}'},
            {'name': 'SELF_LISTENING_ADDRESS', 'value': dns['defaultListeningIP']},
            {'name': 'SELF_HEALTHCHECK_ADDRESS', 'value': dns['default']},
            {'name': 'SELF_PORT', 'value': f'{engine['startPort'] + server_stage_index}'},
            {'name': 'SECRET_KEY_TARGET', 'value': f'{envs['tlsTarget']}/{envs['selfName']}.{fs['keyExt']}'},
            {'name': 'SECRET_CERT_TARGET', 'value': f'{envs['tlsTarget']}/{envs['selfName']}.{fs['certExt']}'},
            {'name': 'SECRET_CA_CERT_TARGET', 'value': f'{envs['tlsTarget']}/{dns['caName']}.{fs['certExt']}'},
            {'name': 'DEST_ADDRESS', 'value': dns['default']},
            {'name': 'DEST_PORT', 'value': f'{dest_port}'},
            {'name': 'THROTTLE_INTERVAL', 'value': f'{envs['throttleInterval']}'},
            {'name': 'UPPER_BOUND', 'value': f'{envs['upperBound']}'}
        ]

        # Create volume mount
        secret_mount: list[dict] = [{
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
    print(f'Adding {template_name}/{deployment['metadata']['name']}.yaml...')
    with open(f'{template_folder}/{deployment['metadata']['name']}.yaml', 'w') as deployment_secret_file:
        deployment_secret_file.write(dump(deployment))


def create_chart(base_folder: Path, project_folder: Path, setup_config: dict, use_case_num: int) -> None:
    # Create subgroups to save space
    stage: dict = setup_config['stage']
    fs: dict = setup_config['fs']
    helm: dict = setup_config['orchestrator']['helm']
    dns: dict = setup_config['dns']
    orchestrator: dict = setup_config['orchestrator']
    engine: dict = setup_config['engine']
    envs: dict = setup_config['envs']

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
    use_case_name: str = f'{stage['useCasePrefix']}-{use_case_num}'
    template_folder: str = f'{base_folder}/{fs['outputFolder']}/{helm['templateFolder']}'
    image_name: str = open(f'{project_folder}/{fs['imageVersionFp']}').read()

    # Create kubernetes namespace
    namespace_hook: dict = {
        'helm.sh/hook': helm['hook'], 'helm.sh/hook-weight': '-2', 'helm.sh/hook-delete-policy': helm['hookPolicy']
    }
    namespace: dict = create_namespace(
        use_case_name, general_level=orchestrator['namespacePolicy'], hook=namespace_hook
    )
    namespace_name: str = namespace['metadata']['name']
    print(f'Adding {helm['templateFolder']}/{namespace_name}.yaml...')
    with open(f'{template_folder}/{namespace_name}.yaml', 'w') as namespace_file:
        namespace_file.write(dump(namespace))

    # Create admission policies
    a_policy_hook: dict = {
        'helm.sh/hook': helm['hook'], 'helm.sh/hook-weight': '-1', 'helm.sh/hook-delete-policy': helm['hookPolicy']
    }
    a_policy_constraints: dict = {
        'resourceRules': [{
            'apiGroups': ['apps'],
            'apiVersions': ['v1'],
            'operations': ['CREATE', 'UPDATE'],
            'resources': ['deployments']
        }]
    }
    a_policy_validations: list[dict] = [{
        'expression': f"object.spec.template.spec.containers.all(c, c.image == '{image_name}')",
        'message': f"Deployment containers can only use the image {image_name}."
    }]
    a_policy_binding_valid_actions: list[str] = ['Deny']
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
    create_secret_templates(
        use_case_name, dns, fs, stage, envs, namespace_name, helm['templateFolder'], template_folder
    )

    # Create deployment
    pod_labels: dict = {
        'app.kubernetes.io/name': f'{use_case_name}-app'
    }
    create_deployment_template(
        use_case_name, namespace_name, orchestrator['replicas'], pod_labels, orchestrator['podRestartPolicy'],
        image_name, stage, engine, dns, envs, fs, helm['templateFolder'], template_folder
    )

    # Create service
    port_bindings: list[dict] = [{
        'port': engine['startPort'] + 1,
        'protocol': 'TCP',
        'targetPort': engine['startPort'] + 1
    }]
    service: dict = create_service(use_case_name, namespace_name, pod_labels, port_bindings)
    print(f'Adding {helm['templateFolder']}/{service['metadata']['name']}.yaml...')
    with open(f'{template_folder}/{service['metadata']['name']}.yaml', 'w') as service_file:
        service_file.write(dump(service))

    # Create ingress
    ingress_paths: list[dict] = [{
        'path': dns['startAPI'],
        'pathType': 'Exact',
        'backend': {
            'service': {
                'name': f'{use_case_name}-service',
                'port': {
                    'number': engine['startPort'] + 1
                }
            }
        }
    }]
    ingress: dict = create_ingress(
        use_case_name, namespace_name, 'nginx', f'v{use_case_num}.{dns['domain']}',
        f'{use_case_name}-{dns['ingressName']}-secret', ingress_paths
    )
    print(f'Adding {helm['templateFolder']}/{ingress['metadata']['name']}.yaml...')
    with open(f'{template_folder}/{ingress['metadata']['name']}.yaml', 'w') as ingress_file:
        ingress_file.write(dump(ingress))

    # Create network policy
    port_bindings: list[dict] = [{
        'port': engine['startPort'] + 1,
        'protocol': 'TCP'
    }]
    network_policy: dict = create_network_policy(
        use_case_name, namespace_name, {'matchLabels': pod_labels}, f'{dns['defaultIP']}/32',
        port_bindings
    )
    print(f'Adding {helm['templateFolder']}/{network_policy['metadata']['name']}.yaml...')
    with open(f'{template_folder}/{network_policy['metadata']['name']}.yaml', 'w') as network_policy_file:
        network_policy_file.write(dump(network_policy))
