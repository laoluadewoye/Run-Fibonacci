from os import environ
from os.path import exists
from enum import StrEnum, auto
from time import time
from base64 import b64encode
from json import dumps
from hashlib import sha256
from requests import request, Response


# Specify desired API and datastore
SERVER_API: str = environ.get('SERVER_API')
SERVER_DATASTORE: str = environ.get('SERVER_DATASTORE')

# Specify default datastore log location and log counts
DATASTORE_FILEPATH: str = environ.get('DATASTORE_FILEPATH')
DATASTORE_DEFAULT_FILEPATH: str = environ.get('DATASTORE_DEFAULT_FILEPATH')
DATASTORE_OPERATIONS_FILEPATH: str = environ.get('DATASTORE_OPERATIONS_FILEPATH')
DATASTORE_LOG_COUNT: int = 0
DATASTORE_DEFAULT_LOG_COUNT: int = 0
DATASTORE_OPERATIONS_LOG_COUNT: int = 0

# Specify datastore network socket
DATASTORE_ADDRESS: str = environ.get('DATASTORE_ADDRESS')
DATASTORE_PORT: str = environ.get('DATASTORE_PORT')

# Specify TLS materials
SECRET_KEY_TARGET: str = environ.get('SECRET_KEY_TARGET')
SECRET_CERT_TARGET: str = environ.get('SECRET_CERT_TARGET')
SECRET_CA_CERT_TARGET: str = environ.get('SECRET_CA_CERT_TARGET')


class APIType(StrEnum):
    REST = auto()
    GRPC = auto()
    SOAP = auto()
    GRAPHQL = auto()
    MQTT = auto()


class DatastoreType(StrEnum):
    DSNONE = 'none'
    DSFILE = 'file'
    ELASTICSTACK = auto()
    MONGODB = auto()
    POSTGRESQL = auto()


class LogType(StrEnum):
    SEND = auto()
    RECEIVE = auto()
    OPERATION = auto()


class LogKind(StrEnum):
    # Events
    ONSTART = auto()
    ONCALL = auto()
    ONLOG = auto()

    # Methods
    TRIGGERSEND = auto()
    MAIN = auto()
    HEALTHCHECK = auto()
    START = auto()
    DATASTORE = auto()


def create_log(log_type: LogType, log_kind: list[LogKind], server_config: dict, details: str) -> dict:
    # Create log
    new_log: dict = {
        'type': log_type.value,
        'kind': ';'.join([lk.value for lk in log_kind]),
        'time': str(time()),
        'config': b64encode(dumps(server_config).encode()).decode(),
        'details': details
    }

    # Hash the contents of the log and return
    new_log['hash'] = sha256(dumps(new_log).encode()).hexdigest()
    return new_log


def save_log(filepath: str, cur_log: dict, config: dict, is_operation: bool = False):
    global DATASTORE_FILEPATH
    global DATASTORE_DEFAULT_FILEPATH
    global DATASTORE_OPERATIONS_FILEPATH
    global DATASTORE_LOG_COUNT
    global DATASTORE_DEFAULT_LOG_COUNT
    global DATASTORE_OPERATIONS_LOG_COUNT

    # Get log count
    if filepath == DATASTORE_FILEPATH:
        DATASTORE_LOG_COUNT += 1
        cur_log_count = DATASTORE_LOG_COUNT
    elif filepath == DATASTORE_DEFAULT_FILEPATH:
        DATASTORE_DEFAULT_LOG_COUNT += 1
        cur_log_count = DATASTORE_DEFAULT_LOG_COUNT
    elif filepath == DATASTORE_OPERATIONS_FILEPATH:
        DATASTORE_OPERATIONS_LOG_COUNT += 1
        cur_log_count = DATASTORE_OPERATIONS_LOG_COUNT
    else:
        cur_log_count = -1
    assert cur_log_count > 0, 'File path should match one of the set paths.'

    # Write down everything
    try:
        if not exists(filepath):
            with open(filepath, 'w') as ds_file:
                ds_file.write('id,' + ','.join(cur_log.keys()) + '\n')
                ds_file.write(f'{cur_log_count},' + ','.join(cur_log.values()) + '\n')
        else:
            with open(filepath, 'a') as ds_file:
                ds_file.write(f'{cur_log_count},' + ','.join(cur_log.values()) + '\n')
        success: bool = True
        details: str ='Log saving event successful.'
    except FileNotFoundError:
        success: bool = False
        details: str = 'Local Datastore location not found.'

    if not is_operation:
        ds_log = create_log(LogType.OPERATION, [LogKind.ONLOG], config, details)
        op_success: bool = save_log(DATASTORE_OPERATIONS_FILEPATH, ds_log, config, is_operation=True)

        return success, op_success
    else:
        return success


def send_log(cur_log: dict, server_config: dict):
    global SERVER_DATASTORE
    global DATASTORE_DEFAULT_FILEPATH
    global DATASTORE_OPERATIONS_FILEPATH
    global DATASTORE_ADDRESS
    global DATASTORE_PORT
    global SECRET_KEY_TARGET
    global SECRET_CERT_TARGET
    global SECRET_CA_CERT_TARGET

    if SERVER_DATASTORE == DatastoreType.DSNONE.value: # Save to local temp CSV
        save_log(DATASTORE_DEFAULT_FILEPATH, cur_log, server_config)
    elif SERVER_DATASTORE == DatastoreType.DSFILE.value:  # Send to remote CSV
        response: Response = request(
            method='POST',
            url=f'https://{DATASTORE_ADDRESS}:{DATASTORE_PORT}/datastore',
            json=cur_log,
            cert=(SECRET_CERT_TARGET, SECRET_KEY_TARGET),
            verify=SECRET_CA_CERT_TARGET
        )
        ds_log = create_log(
            LogType.OPERATION, [LogKind.ONLOG], server_config,
            f'Return info for datastore sending: {response.json()}'
        )
        save_log(DATASTORE_OPERATIONS_FILEPATH, ds_log, server_config, is_operation=True)
    elif SERVER_DATASTORE == DatastoreType.ELASTICSTACK.value:  # Send to remote elasticstack
        pass
    elif SERVER_DATASTORE == DatastoreType.MONGODB.value:  # Send to remote MongoDB
        pass
    elif SERVER_DATASTORE == DatastoreType.POSTGRESQL.value:  # Send to remote PostgreSQL
        pass
    else:  # Error out
        pass


def report_log(log_type: LogType, log_kind: list[LogKind], server_config: dict, details: str) -> None:
    # Send details to output
    print(details, flush=True)

    # Create log
    new_log = create_log(log_type, log_kind, server_config, details)

    # Send log to datastore
    send_log(new_log, server_config)


'''
Type of logs

1) Sends - Logs that are sent out by the server
2) Receives - Logs that are retrieved by the server
3) Operations - Logs that are generated by the server

Kinds of logs

1) OnStart - Logs that are created when the server is first started
2) OnCall - Logs that are created when the server API is called

Log fields

* ID - Incrementing number autogenerated by whatever datastore is used
* Hash - The Hash of the log in SHA256
* Type - The type of log
* Kind - The kind(s) of log
* Time - The timestamp the log was recorded in UNIX epoch seconds
* Config - The configuration of the server in base 64
* Details - The details of the log in base 64
'''
