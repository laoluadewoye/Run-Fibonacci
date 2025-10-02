def create_namespace(name: str, general_level: str = 'privileged', general_version: str = 'v1.34',
                     enforce_level: str = None, enforce_version: str = None, audit_level: str = None,
                     audit_version: str = None, warn_level: str = None, warn_version: str = None,
                     hook: dict = None) -> dict:
    # Set levels
    if enforce_level is None:
        enforce_level = general_level
    if audit_level is None:
        audit_level = general_level
    if warn_level is None:
        warn_level = general_level

    # Set versions
    if enforce_version is None:
        enforce_version = general_version
    if audit_version is None:
        audit_version = general_version
    if warn_version is None:
        warn_version = general_version

    # Create namespace
    namespace_config = {
        'apiVersion': 'v1',
        'kind': 'Namespace',
        'metadata': {
            'name': f'{name}-namespace',
            'labels': {
                'pod-security.kubernetes.io/enforce': enforce_level,
                'pod-security.kubernetes.io/enforce-version': enforce_version,
                'pod-security.kubernetes.io/audit': audit_level,
                'pod-security.kubernetes.io/audit-version': audit_version,
                'pod-security.kubernetes.io/warn': warn_level,
                'pod-security.kubernetes.io/warn-version': warn_version
            }
        }
    }

    # Check for hooks
    if hook is not None:
        namespace_config['metadata']['annotations'] = {k:v for k, v in hook.items()}

    # Return namespace
    return namespace_config


def create_validating_admission_policy(name: str, failure_policy: str, constraints: dict, validations: list[dict],
                                       validation_actions: list[str], namespace_name: str,
                                       hook: dict = None) -> tuple[dict, dict]:
    # Create policy
    policy_config: dict = {
        'apiVersion': 'admissionregistration.k8s.io/v1',
        'kind': 'ValidatingAdmissionPolicy',
        'metadata': {
            'name': f'{name}-admission-policy',
        },
        'spec': {
            'failurePolicy': failure_policy,
            'matchConstraints': constraints,
            'validations': validations
        }
    }

    # Create policy binding
    policy_binding_config: dict = {
        'apiVersion': 'admissionregistration.k8s.io/v1',
        'kind': 'ValidatingAdmissionPolicyBinding',
        'metadata': {
            'name': f'{name}-admission-policy-binding'
        },
        'spec': {
            'policyName': f'{name}-admission-policy',
            'validationActions': validation_actions,
            'matchResources': {
                'namespaceSelector': {
                    'matchExpressions': [{
                        'key': 'kubernetes.io/metadata.name',
                        'operator': 'In',
                        'values': [namespace_name]
                    }]
                }
            }
        }
    }

    # Check for hooks
    if hook is not None:
        policy_config['metadata']['annotations'] = {k:v for k, v in hook.items()}
        policy_binding_config['metadata']['annotations'] = {k:v for k, v in hook.items()}

    # Return admission policy and admission policy binding
    return policy_config, policy_binding_config


def create_secret(name: str, namespace_name: str, secret_type: str, secret_data: dict, labels: dict = None,
                  is_encoded: bool = True, is_immutable: bool = True) -> dict:
    # Create secret
    secret_config: dict = {
        'apiVersion': 'v1',
        'kind': 'Secret',
        'metadata': {
            'name': f'{name}-secret',
            'namespace': namespace_name,
        },
        'type': secret_type,
        'immutable': is_immutable
    }

    # Add secret data based desire for encoding
    if is_encoded:
        secret_config['data'] = secret_data
    else:
        secret_config['stringData'] = secret_data

    # Add labels if needed
    if labels is not None:
        secret_config['metadata']['labels'] = labels

    # Return secret
    return secret_config


def create_deployment(name: str, namespace_name: str, replica_count: int, pod_labels: dict, restart_policy: str,
                      node_selector: dict = None, labels: dict = None) -> dict:
    # Create deployment
    deployment_config: dict = {
        'apiVersion': 'apps/v1',
        'kind': 'Deployment',
        'metadata': {
            'name': f'{name}-deployment',
            'namespace': namespace_name
        },
        'spec': {
            'replicas': replica_count,
            'selector': {'matchLabels': pod_labels},
            'template': {
                'metadata': {'labels': pod_labels},
                'spec': {
                    'restartPolicy': restart_policy,
                    'containers': [],
                    'volumes': [],
                    'securityContext': {
                        'runAsNonRoot': True,
                        'runAsUser': 1000,
                        'seccompProfile': {
                            'type': 'RuntimeDefault'
                        }
                    },
                }
            }
        }
    }

    # Add node selector if needed
    if node_selector is not None:
        deployment_config['spec']['template']['spec']['nodeSelector'] = node_selector

    # Add labels if needed
    if labels is not None:
        deployment_config['metadata']['labels'] = labels

    # Return deployment
    return deployment_config


def create_container(name: str, image_name: str, port_bindings: list[dict], env_settings: list[dict],
                     mounts: list[dict], probe_settings: dict) -> dict:
    return {
        'name': name,
        'image': image_name,
        'ports': port_bindings,
        'env': env_settings,
        'volumeMounts': mounts,
        'livenessProbe': probe_settings,
        'securityContext': {
            'allowPrivilegeEscalation': False,
            'capabilities': {'drop': ['ALL'], 'add': ['NET_BIND_SERVICE']},
            'privileged': False,
            'readOnlyRootFilesystem': False
        }
    }


def create_secret_volume(name: str, secret_name: str) -> dict:
    return {'name': name, 'secret': {'secretName': secret_name}}


def create_service(name: str, namespace_name: str, selector: dict, ports: list[dict], labels: dict = None) -> dict:
    # Create service
    service_config: dict = {
        'apiVersion': 'v1',
        'kind': 'Service',
        'metadata': {
            'name': f'{name}-service',
            'namespace': namespace_name,
        },
        'spec': {
            'selector': selector,
            'ports': ports,
        }
    }

    # Add labels if needed
    if labels is not None:
        service_config['metadata']['labels'] = labels

    # Return service
    return service_config


def create_ingress(name: str, namespace_name: str, ingress_class: str, ingress_hostname: str, ingress_secret: str,
                   ingress_paths: list[dict], labels: dict = None) -> dict:
    # Create ingress
    ingress_config: dict = {
        'apiVersion': 'networking.k8s.io/v1',
        'kind': 'Ingress',
        'metadata': {
            'name': f'{name}-ingress',
            'namespace': namespace_name,
            'annotations': {
                'nginx.ingress.kubernetes.io/backend-protocol': 'HTTPS'
            }
        },
        'spec': {
            'ingressClassName': ingress_class,
            'tls': [{
                'hosts': [ingress_hostname],
                'secretName': ingress_secret
            }],
            'rules': [{
                'host': ingress_hostname,
                'http': {
                    'paths': ingress_paths
                }
            }]
        }
    }

    # Add labels if needed
    if labels is not None:
        ingress_config['metadata']['labels'] = labels

    # Return ingress
    return ingress_config


def create_network_policy(name: str, namespace_name: str, pod_selector: dict, external_ip: str, ports: list[dict],
                          labels: dict = None) -> dict:
    # Create network policy
    network_policy_config: dict = {
        'apiVersion': 'networking.k8s.io/v1',
        'kind': 'NetworkPolicy',
        'metadata': {
            'name': f'{name}-network-policy',
            'namespace': namespace_name,
        },
        'spec': {
            'podSelector': pod_selector,
            'policyTypes': ['Ingress', 'Egress'],
            'ingress': [{
                'from': [
                    {'ipBlock': {'cidr': external_ip}},
                    {
                        'namespaceSelector': {
                            'matchExpressions': [{
                                'key': 'kubernetes.io/metadata.name',
                                'operator': 'In',
                                'values': [namespace_name]
                            }]
                        }
                    }
                ],
                'ports': ports
            }],
            'egress': [{
                'to': [
                    {'ipBlock': {'cidr': external_ip}},
                    {
                        'namespaceSelector': {
                            'matchExpressions': [{
                                'key': 'kubernetes.io/metadata.name',
                                'operator': 'In',
                                'values': [namespace_name]
                            }]
                        }
                    }
                ],
                'ports': ports
            }]
        }
    }

    # Add labels if needed
    if labels is not None:
        network_policy_config['metadata']['labels'] = labels

    # Return network policy
    return network_policy_config
