def create_namespace(name, general_level='privileged', general_version='v1.34', enforce_level=None,
                     enforce_version=None, audit_level=None, audit_version=None, warn_level=None, warn_version=None):
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

    # Return namespace
    return {
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


def create_validating_admission_policy(name, failure_policy, constraints, validations, validation_actions,
                                       namespace_name):
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

    # Return policy and policy binding
    return policy_config, policy_binding_config


def create_secret(name, namespace_name, secret_type, secret_data, labels=None, is_immutable=True):
    # Create config
    secret_config = {
        'apiVersion': 'v1',
        'kind': 'Secret',
        'metadata': {
            'name': f'{name}-secret',
            'namespace': namespace_name,
        },
        'type': secret_type,
        'immutable': is_immutable,
        'data': secret_data
    }

    # Add labels if needed
    if labels is not None:
        secret_config['metadata']['labels'] = labels

    # Return secret
    return secret_config


def create_service(name, namespace_name, selector, ports, labels=None):
    # Create config
    service_config = {
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


def create_ingress(name, namespace_name, ingress_class, ingress_hostname, ingress_secret, ingress_paths, labels=None):
    # Create config
    ingress_config = {
        'apiVersion': 'networking.k8s.io/v1',
        'kind': 'Ingress',
        'metadata': {
            'name': f'{name}-ingress',
            'namespace': namespace_name,
        },
        'spec': {
            'ingressClassName': ingress_class,
            'TLS': [{
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


def create_network_policy(name, namespace_name, pod_selector, external_ip, ports, labels=None):
    # Create config
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
                '_to': [
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
